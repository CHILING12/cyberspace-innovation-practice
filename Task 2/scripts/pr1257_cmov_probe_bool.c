#define SECP256K1_BUILD 1
#include "include/secp256k1.h"

#define SECP256K1_WIDEMUL_INT128 1
#include "src/field_5x52_impl.h"

#if defined(_MSC_VER)
#define NOINLINE __declspec(noinline)
#else
#define NOINLINE __attribute__((noinline))
#endif

NOINLINE void probe_fe_cmov_bool(secp256k1_fe *r, const secp256k1_fe *a, int secret) {
    secp256k1_fe_cmov(r, a, secret != 0);
}

NOINLINE void probe_fe_storage_cmov_bool(secp256k1_fe_storage *r, const secp256k1_fe_storage *a, int secret) {
    secp256k1_fe_storage_cmov(r, a, secret != 0);
}
