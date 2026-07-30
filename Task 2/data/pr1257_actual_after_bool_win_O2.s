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
	push	rax
	.seh_stackalloc 8
	.seh_endprologue
	xor	eax, eax
	test	r8d, r8d
	setne	al
	mov	dword ptr [rsp + 4], eax
	movsxd	r10, dword ptr [rsp + 4]
	lea	r8, [r10 - 1]
	neg	r10
	mov	r9, qword ptr [rcx]
	and	r9, r8
	mov	rax, qword ptr [rdx]
	and	rax, r10
	or	rax, r9
	mov	qword ptr [rcx], rax
	mov	r9, qword ptr [rcx + 8]
	and	r9, r8
	mov	rax, qword ptr [rdx + 8]
	and	rax, r10
	or	rax, r9
	mov	qword ptr [rcx + 8], rax
	mov	r9, qword ptr [rcx + 16]
	and	r9, r8
	mov	rax, qword ptr [rdx + 16]
	and	rax, r10
	or	rax, r9
	mov	qword ptr [rcx + 16], rax
	mov	r9, qword ptr [rcx + 24]
	and	r9, r8
	mov	rax, qword ptr [rdx + 24]
	and	rax, r10
	or	rax, r9
	mov	qword ptr [rcx + 24], rax
	and	r8, qword ptr [rcx + 32]
	and	r10, qword ptr [rdx + 32]
	or	r10, r8
	mov	qword ptr [rcx + 32], r10
	pop	rax
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
	push	rax
	.seh_stackalloc 8
	.seh_endprologue
	xor	eax, eax
	test	r8d, r8d
	setne	al
	mov	dword ptr [rsp + 4], eax
	movsxd	r10, dword ptr [rsp + 4]
	lea	r8, [r10 - 1]
	neg	r10
	mov	r9, qword ptr [rcx]
	and	r9, r8
	mov	rax, qword ptr [rdx]
	and	rax, r10
	or	rax, r9
	mov	qword ptr [rcx], rax
	mov	r9, qword ptr [rcx + 8]
	and	r9, r8
	mov	rax, qword ptr [rdx + 8]
	and	rax, r10
	or	rax, r9
	mov	qword ptr [rcx + 8], rax
	mov	r9, qword ptr [rcx + 16]
	and	r9, r8
	mov	rax, qword ptr [rdx + 16]
	and	rax, r10
	or	rax, r9
	mov	qword ptr [rcx + 16], rax
	and	r8, qword ptr [rcx + 24]
	and	r10, qword ptr [rdx + 24]
	or	r10, r8
	mov	qword ptr [rcx + 24], r10
	pop	rax
	ret
	.seh_endproc
                                        # -- End function
	.addrsig
