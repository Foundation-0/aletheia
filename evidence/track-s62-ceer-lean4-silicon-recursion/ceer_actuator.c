/*
 * ceer_actuator.c — Deterministic micro-scale CPU/memory/thermal actuator for
 * 3-cycle Calculational-Experimental Epistemic Recursion (CEER).
 *
 * Implements four controllable micro-scale levers with exact integer counters:
 *   1. compute  <duration_ms> <cpu0,cpu1,...> : pinned physical-core integer ALU load
 *   2. memchase <duration_ms> <cpu_id> <bytes>: Sattolo single-cycle pointer chasing
 *                                               (64-byte cache-line stride, defeats prefetchers)
 *   3. ramp     <step_ms> <p0,p1,...>         : deterministic multi-step pinned core ramp
 *   4. idle     <duration_ms>                 : quiet baseline sleep window
 *
 * Build (in ephemeral scratch directory; zero compiled ELF committed):
 *   gcc -O3 -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -pthread ceer_actuator.c -o ceer_actuator
 *
 * Emits a single-line strict integer JSON summary to stdout. Zero floating-point math.
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_WORKERS 16
#define CACHE_LINE_BYTES 64u

static uint64_t now_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        return 0;
    }
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static uint64_t splitmix64_next(uint64_t *state) {
    uint64_t z = (*state += 0x9e3779b97f4a7c15ULL);
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

static int parse_u64_strict(const char *s, uint64_t *out) {
    if (s == NULL || s[0] == '\0') {
        return -1;
    }
    uint64_t acc = 0;
    for (const char *p = s; *p != '\0'; ++p) {
        if (*p < '0' || *p > '9') {
            return -1;
        }
        uint64_t d = (uint64_t)(*p - '0');
        if (acc > (UINT64_MAX - d) / 10ULL) {
            return -1;
        }
        acc = acc * 10ULL + d;
    }
    *out = acc;
    return 0;
}

static int parse_cpu_list(const char *spec, int *cpus, int max_n) {
    if (spec == NULL || spec[0] == '\0') {
        return -1;
    }
    int count = 0;
    const char *p = spec;
    while (*p != '\0') {
        if (count >= max_n) {
            return -1;
        }
        char buf[32];
        size_t len = 0;
        while (*p != '\0' && *p != ',') {
            if (len + 1 >= sizeof(buf)) {
                return -1;
            }
            buf[len++] = *p++;
        }
        buf[len] = '\0';
        uint64_t val = 0;
        if (parse_u64_strict(buf, &val) != 0 || val >= 256ULL) {
            return -1;
        }
        cpus[count++] = (int)val;
        if (*p == ',') {
            ++p;
            if (*p == '\0') {
                return -1;
            }
        }
    }
    return count;
}

static int pin_current_thread(int cpu_id) {
    cpu_set_t mask;
    CPU_ZERO(&mask);
    CPU_SET(cpu_id, &mask);
    return sched_setaffinity(0, sizeof(mask), &mask);
}

typedef struct {
    int cpu_id;
    uint64_t end_ns;
    uint64_t ops;
    uint64_t sink;
    int pin_ok;
} ComputeArg;

static void *compute_worker(void *raw) {
    ComputeArg *arg = (ComputeArg *)raw;
    arg->pin_ok = (pin_current_thread(arg->cpu_id) == 0) ? 1 : 0;
    uint64_t a = 0x243f6a8885a308d3ULL ^ (uint64_t)(arg->cpu_id + 1);
    uint64_t b = 0x13198a2e03707344ULL ^ ((uint64_t)(arg->cpu_id + 1) << 17);
    uint64_t c = 0xa4093822299f31d0ULL;
    uint64_t d = 0x082efa98ec4e6c89ULL;
    uint64_t ops = 0;

    while (now_ns() < arg->end_ns) {
        for (int k = 0; k < 4096; ++k) {
            a = a * 6364136223846793005ULL + 1442695040888963407ULL;
            b = (b ^ (a >> 13)) * 2862933555777941757ULL + 3037000493ULL;
            c = c + ((a ^ b) >> 7) + (d << 3);
            d = d ^ (c * 0x9e3779b97f4a7c15ULL);
            a ^= (d >> 19);
            b += (c >> 11);
        }
        ops += 4096ULL * 12ULL;
    }
    arg->ops = ops;
    arg->sink = a ^ b ^ c ^ d;
    return NULL;
}

static int run_compute_window(uint64_t duration_ms, const int *cpus, int n_cpus,
                              uint64_t *total_ops_out, uint64_t *elapsed_ns_out,
                              uint64_t *sink_out, int *all_pinned_out) {
    if (n_cpus < 1 || n_cpus > MAX_WORKERS) {
        return -1;
    }
    pthread_t th[MAX_WORKERS];
    ComputeArg args[MAX_WORKERS];
    uint64_t t0 = now_ns();
    uint64_t end_ns = t0 + duration_ms * 1000000ULL;

    for (int i = 0; i < n_cpus; ++i) {
        args[i].cpu_id = cpus[i];
        args[i].end_ns = end_ns;
        args[i].ops = 0;
        args[i].sink = 0;
        args[i].pin_ok = 0;
        if (pthread_create(&th[i], NULL, compute_worker, &args[i]) != 0) {
            for (int j = 0; j < i; ++j) {
                pthread_join(th[j], NULL);
            }
            return -1;
        }
    }
    uint64_t tot_ops = 0;
    uint64_t sink = 0;
    int all_pin = 1;
    for (int i = 0; i < n_cpus; ++i) {
        pthread_join(th[i], NULL);
        tot_ops += args[i].ops;
        sink ^= args[i].sink;
        if (!args[i].pin_ok) {
            all_pin = 0;
        }
    }
    uint64_t t1 = now_ns();
    *total_ops_out = tot_ops;
    *elapsed_ns_out = (t1 > t0) ? (t1 - t0) : 1ULL;
    *sink_out = sink;
    *all_pinned_out = all_pin;
    return 0;
}

typedef struct {
    uint64_t next_idx;
    uint64_t pad[7];
} CacheLineNode;

static int run_memchase_window(uint64_t duration_ms, int cpu_id, uint64_t bytes) {
    if (bytes < 4096ULL || bytes > (256ULL << 20)) {
        fprintf(stderr, "ERROR: memchase bytes out of bounds [4096, 268435456]\n");
        return 2;
    }
    size_t n_nodes = (size_t)(bytes / sizeof(CacheLineNode));
    if (n_nodes < 64) {
        fprintf(stderr, "ERROR: too few cache-line nodes\n");
        return 2;
    }
    int pin_ok = (pin_current_thread(cpu_id) == 0) ? 1 : 0;

    CacheLineNode *buf = NULL;
    if (posix_memalign((void **)&buf, CACHE_LINE_BYTES, n_nodes * sizeof(CacheLineNode)) != 0 || buf == NULL) {
        fprintf(stderr, "ERROR: posix_memalign failed\n");
        return 2;
    }
    uint64_t *perm = (uint64_t *)malloc(n_nodes * sizeof(uint64_t));
    if (perm == NULL) {
        free(buf);
        fprintf(stderr, "ERROR: malloc perm failed\n");
        return 2;
    }
    /* Sattolo algorithm: guaranteed single Hamiltonian cycle over all n_nodes cache lines */
    for (size_t i = 0; i < n_nodes; ++i) {
        perm[i] = (uint64_t)i;
    }
    uint64_t rng = 0x62ceef001ULL ^ bytes ^ ((uint64_t)cpu_id << 32);
    for (size_t i = n_nodes - 1; i > 0; --i) {
        size_t j = (size_t)(splitmix64_next(&rng) % i);
        uint64_t tmp = perm[i];
        perm[i] = perm[j];
        perm[j] = tmp;
    }
    for (size_t i = 0; i < n_nodes; ++i) {
        buf[i].next_idx = perm[i];
        for (int p = 0; p < 7; ++p) {
            buf[i].pad[p] = perm[i] ^ (uint64_t)p;
        }
    }
    free(perm);

    /* Warm fault pages cleanly once before timed window */
    uint64_t idx = 0;
    for (size_t i = 0; i < n_nodes; ++i) {
        idx = buf[idx].next_idx;
    }

    uint64_t t0 = now_ns();
    uint64_t end_ns = t0 + duration_ms * 1000000ULL;
    uint64_t chases = 0;
    while (now_ns() < end_ns) {
        for (int k = 0; k < 2048; ++k) {
            idx = buf[idx].next_idx;
            idx = buf[idx].next_idx;
            idx = buf[idx].next_idx;
            idx = buf[idx].next_idx;
        }
        chases += 2048ULL * 4ULL;
    }
    uint64_t t1 = now_ns();
    uint64_t elapsed_ns = (t1 > t0) ? (t1 - t0) : 1ULL;
    free(buf);

    printf("{\"mode\":\"memchase\",\"cpu_id\":%d,\"pin_ok\":%d,\"bytes\":%" PRIu64
           ",\"nodes\":%zu,\"chases\":%" PRIu64 ",\"elapsed_ns\":%" PRIu64
           ",\"sink\":%" PRIu64 "}\n",
           cpu_id, pin_ok, bytes, n_nodes, chases, elapsed_ns, idx);
    return 0;
}

static int run_idle_window(uint64_t duration_ms) {
    uint64_t t0 = now_ns();
    struct timespec req;
    req.tv_sec = (time_t)(duration_ms / 1000ULL);
    req.tv_nsec = (long)((duration_ms % 1000ULL) * 1000000ULL);
    while (nanosleep(&req, &req) == -1 && errno == EINTR) {
    }
    uint64_t t1 = now_ns();
    uint64_t elapsed_ns = (t1 > t0) ? (t1 - t0) : 1ULL;
    printf("{\"mode\":\"idle\",\"duration_ms\":%" PRIu64 ",\"elapsed_ns\":%" PRIu64 "}\n",
           duration_ms, elapsed_ns);
    return 0;
}

static int run_ramp_sequence(uint64_t step_ms, const int *step_counts, int n_steps) {
    static const int phys_cpus[8] = {0, 1, 2, 3, 4, 5, 6, 7};
    uint64_t total_ops = 0;
    uint64_t total_sink = 0;
    uint64_t t0 = now_ns();
    int all_pin = 1;
    for (int s = 0; s < n_steps; ++s) {
        int p = step_counts[s];
        if (p == 0) {
            struct timespec req;
            req.tv_sec = (time_t)(step_ms / 1000ULL);
            req.tv_nsec = (long)((step_ms % 1000ULL) * 1000000ULL);
            while (nanosleep(&req, &req) == -1 && errno == EINTR) {
            }
            continue;
        }
        if (p < 1 || p > 8) {
            fprintf(stderr, "ERROR: ramp step core count out of [0,8]\n");
            return 2;
        }
        uint64_t ops = 0, ens = 0, sk = 0;
        int pk = 0;
        if (run_compute_window(step_ms, phys_cpus, p, &ops, &ens, &sk, &pk) != 0) {
            return 2;
        }
        total_ops += ops;
        total_sink ^= sk;
        if (!pk) {
            all_pin = 0;
        }
    }
    uint64_t t1 = now_ns();
    uint64_t elapsed_ns = (t1 > t0) ? (t1 - t0) : 1ULL;
    printf("{\"mode\":\"ramp\",\"step_ms\":%" PRIu64 ",\"n_steps\":%d,\"all_pinned\":%d"
           ",\"retired_ops\":%" PRIu64 ",\"elapsed_ns\":%" PRIu64 ",\"sink\":%" PRIu64 "}\n",
           step_ms, n_steps, all_pin, total_ops, elapsed_ns, total_sink);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: ceer_actuator <compute|memchase|ramp|idle> <duration_ms> [args...]\n");
        return 2;
    }
    const char *mode = argv[1];
    uint64_t dur_ms = 0;
    if (parse_u64_strict(argv[2], &dur_ms) != 0 || dur_ms < 50ULL || dur_ms > 60000ULL) {
        fprintf(stderr, "ERROR: duration_ms must be integer in [50, 60000]\n");
        return 2;
    }
    if (strcmp(mode, "idle") == 0) {
        return run_idle_window(dur_ms);
    }
    if (strcmp(mode, "compute") == 0) {
        if (argc != 4) {
            fprintf(stderr, "usage: ceer_actuator compute <duration_ms> <cpu0,cpu1,...>\n");
            return 2;
        }
        int cpus[MAX_WORKERS];
        int n = parse_cpu_list(argv[3], cpus, MAX_WORKERS);
        if (n < 1) {
            fprintf(stderr, "ERROR: invalid cpu list\n");
            return 2;
        }
        uint64_t ops = 0, ens = 0, sk = 0;
        int all_pin = 0;
        if (run_compute_window(dur_ms, cpus, n, &ops, &ens, &sk, &all_pin) != 0) {
            fprintf(stderr, "ERROR: compute window failed\n");
            return 2;
        }
        printf("{\"mode\":\"compute\",\"n_cpus\":%d,\"all_pinned\":%d,\"retired_ops\":%" PRIu64
               ",\"elapsed_ns\":%" PRIu64 ",\"sink\":%" PRIu64 "}\n",
               n, all_pin, ops, ens, sk);
        return 0;
    }
    if (strcmp(mode, "memchase") == 0) {
        if (argc != 5) {
            fprintf(stderr, "usage: ceer_actuator memchase <duration_ms> <cpu_id> <bytes>\n");
            return 2;
        }
        uint64_t cpu_u = 0, bytes = 0;
        if (parse_u64_strict(argv[3], &cpu_u) != 0 || cpu_u >= 256ULL ||
            parse_u64_strict(argv[4], &bytes) != 0) {
            fprintf(stderr, "ERROR: invalid memchase args\n");
            return 2;
        }
        return run_memchase_window(dur_ms, (int)cpu_u, bytes);
    }
    if (strcmp(mode, "ramp") == 0) {
        if (argc != 4) {
            fprintf(stderr, "usage: ceer_actuator ramp <step_ms> <p0,p1,...>\n");
            return 2;
        }
        int steps[MAX_WORKERS];
        int n = parse_cpu_list(argv[3], steps, MAX_WORKERS);
        if (n < 2) {
            fprintf(stderr, "ERROR: ramp needs >= 2 steps\n");
            return 2;
        }
        return run_ramp_sequence(dur_ms, steps, n);
    }
    fprintf(stderr, "ERROR: unknown mode %s\n", mode);
    return 2;
}
