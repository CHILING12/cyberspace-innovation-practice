#define SECP256K1_BUILD 1
#include "include/secp256k1.h"

#define SECP256K1_WIDEMUL_INT128 1
#include "src/int128_impl.h"
#include "src/field_5x52_impl.h"

#if defined(_MSC_VER)
#define NOINLINE __declspec(noinline)
#else
#define NOINLINE __attribute__((noinline))
#endif

NOINLINE void probe_fe_mul_inner(unsigned long long *r, const unsigned long long *a, const unsigned long long *b) {
    secp256k1_fe_mul_inner(r, a, b);
}
