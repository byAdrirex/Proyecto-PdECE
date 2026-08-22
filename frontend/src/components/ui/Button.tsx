import { forwardRef, type ButtonHTMLAttributes, type PropsWithChildren } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'quiet';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export const Button = forwardRef<HTMLButtonElement, PropsWithChildren<ButtonProps>>(function Button({
  children,
  className = '',
  variant = 'primary',
  type = 'button',
  ...props
}: PropsWithChildren<ButtonProps>, ref) {
  return (
    <button ref={ref} type={type} className={`button button--${variant} ${className}`.trim()} {...props}>
      {children}
    </button>
  );
});
