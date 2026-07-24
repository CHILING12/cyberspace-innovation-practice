# Makefile — 对称密码算法软件实现
#
# 目标:
#   make all         构建所有目标
#   make test        运行正确性测试
#   make bench       运行性能基准测试
#   make clean       清理构建产物
#
# 编译选项:
#   -O2              基本优化
#   -O3 -march=native 最高优化 + 本地指令集
#   -O3 -mavx2 -maes -mpclmul  指定 ISA intrinsic

CC       = gcc
CFLAGS   = -Wall -Wextra -std=c11
LDFLAGS  = -lm

# 优化级别（可通过 make OPT=O3 覆盖）
OPT      = O2
ARCH     = -march=native

# 源代码文件
SRCS     = common.c aes.c sm4.c gift128.c twine.c modes.c benchmark.c
OBJS     = $(SRCS:.c=.o)
TARGET   = cipher_test

# Intel intrinsics 需要特定体系结构标志
ifeq ($(shell uname -m), x86_64)
    CFLAGS += -maes -mpclmul -mssse3
endif

# AVX2 和 VAES 可选（需要 CPU 支持）
# CFLAGS += -mavx2 -mvaes -mvpclmulqdq -mgfni

.PHONY: all test bench clean help

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -$(OPT) $(ARCH) -o $@ $^ $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -$(OPT) $(ARCH) -c -o $@ $<

# 不同优化级别下的编译目标
opt-O2:
	$(MAKE) clean
	$(MAKE) all OPT=O2

opt-O3:
	$(MAKE) clean
	$(MAKE) all OPT=O3

opt-O3-native:
	$(MAKE) clean
	$(MAKE) all OPT=O3 ARCH="-march=native"

opt-O3-lto:
	$(MAKE) clean
	$(MAKE) all OPT=O3 ARCH="-march=native" CFLAGS="$(CFLAGS) -flto"

test: $(TARGET)
	./$(TARGET)

bench: $(TARGET)
	./$(TARGET) --bench

# 运行所有编译配置下的测试
test-all: opt-O2 opt-O3 opt-O3-native
	@echo "=== Testing with -O2 ==="
	@./$(TARGET)
	@echo "=== Testing with -O3 ==="
	@./$(TARGET)
	@echo "=== Testing with -O3 -march=native ==="
	@./$(TARGET)

clean:
	rm -f $(OBJS) $(TARGET)

help:
	@echo "Symmetric Cipher Implementation - Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all          Build test binary (default)"
	@echo "  test         Build and run correctness tests"
	@echo "  bench        Build and run performance benchmarks"
	@echo "  clean        Remove build artifacts"
	@echo "  opt-O2       Build with -O2"
	@echo "  opt-O3       Build with -O3"
	@echo "  opt-O3-native Build with -O3 -march=native"
	@echo "  opt-O3-lto   Build with -O3 -march=native -flto"
	@echo "  test-all     Build and test with all optimization levels"
	@echo "  help         Show this help"
