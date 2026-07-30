	.text
	.def	@feat.00;
	.scl	3;
	.type	0;
	.endef
	.globl	@feat.00
.set @feat.00, 0
	.intel_syntax noprefix
	.file	"pr1257_cmov_probe_bool.c"
	.def	probe_fe_cmov_bool;
	.scl	2;
	.type	32;
	.endef
	.globl	probe_fe_cmov_bool              # -- Begin function probe_fe_cmov_bool
	.p2align	4, 0x90
probe_fe_cmov_bool:                     # @probe_fe_cmov_bool
.seh_proc probe_fe_cmov_bool
# %bb.0:
	push	r14
	.seh_pushreg r14
	push	rsi
	.seh_pushreg rsi
	push	rdi
	.seh_pushreg rdi
	push	rbx
	.seh_pushreg rbx
	.seh_endprologue
	lea	r9, [rcx + 8]
	lea	rax, [rdx + 8]
	lea	r10, [rcx + 16]
	lea	r11, [rdx + 16]
	lea	rsi, [rcx + 24]
	lea	rdi, [rdx + 24]
	lea	r14, [rcx + 32]
	lea	rbx, [rdx + 32]
	test	r8d, r8d
	cmove	rdx, rcx
	mov	rdx, qword ptr [rdx]
	mov	qword ptr [rcx], rdx
	cmove	rax, r9
	mov	rax, qword ptr [rax]
	mov	qword ptr [rcx + 8], rax
	cmove	r11, r10
	mov	rax, qword ptr [r11]
	mov	qword ptr [rcx + 16], rax
	cmove	rdi, rsi
	mov	rax, qword ptr [rdi]
	mov	qword ptr [rcx + 24], rax
	cmove	rbx, r14
	mov	rax, qword ptr [rbx]
	mov	qword ptr [rcx + 32], rax
	pop	rbx
	pop	rdi
	pop	rsi
	pop	r14
	ret
	.seh_endproc
                                        # -- End function
	.def	probe_fe_storage_cmov_bool;
	.scl	2;
	.type	32;
	.endef
	.globl	probe_fe_storage_cmov_bool      # -- Begin function probe_fe_storage_cmov_bool
	.p2align	4, 0x90
probe_fe_storage_cmov_bool:             # @probe_fe_storage_cmov_bool
.seh_proc probe_fe_storage_cmov_bool
# %bb.0:
	push	rsi
	.seh_pushreg rsi
	push	rdi
	.seh_pushreg rdi
	.seh_endprologue
	lea	r9, [rcx + 8]
	lea	rax, [rdx + 8]
	lea	r10, [rcx + 16]
	lea	r11, [rdx + 16]
	lea	rsi, [rcx + 24]
	lea	rdi, [rdx + 24]
	test	r8d, r8d
	cmove	rdx, rcx
	mov	rdx, qword ptr [rdx]
	mov	qword ptr [rcx], rdx
	cmove	rax, r9
	mov	rax, qword ptr [rax]
	mov	qword ptr [rcx + 8], rax
	cmove	r11, r10
	mov	rax, qword ptr [r11]
	mov	qword ptr [rcx + 16], rax
	cmove	rdi, rsi
	mov	rax, qword ptr [rdi]
	mov	qword ptr [rcx + 24], rax
	pop	rdi
	pop	rsi
	ret
	.seh_endproc
                                        # -- End function
	.addrsig
