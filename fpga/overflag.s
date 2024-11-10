	.text
	.globl	overflow_test
	.type	overflow_test, @function
overflow_test:
.LFB0:
	pushq	%rbp
	movq	%rsp, %rbp
	movl	%esi, %eax
	movq	%rdx, -16(%rbp)
	movq	%rcx, -24(%rbp)
	movl	%edi, %edx
	movb	%dl, -4(%rbp)
	movb	%al, -8(%rbp)

    sub     %al, %dl
    jo      overflow

no_overflow:
	movq	-24(%rbp), %rax
	movb	$0, (%rax)
    jmp     finish
overflow:
	movq	-24(%rbp), %rax
	movb	$1, (%rax)
finish:
	movq	-16(%rbp), %rax
	movb	%dl, (%rax)

	nop
	popq	%rbp
	ret
	.section	.note.GNU-stack,"",@progbits
