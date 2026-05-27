import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-sm border border-transparent text-sm font-medium font-sans whitespace-nowrap transition-all duration-150 outline-none select-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-40 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground border-primary hover:bg-primary/90 hover:border-primary/90",
        outline:
          "border-border bg-transparent text-foreground hover:bg-muted hover:border-foreground/25",
        secondary:
          "bg-secondary text-secondary-foreground border-secondary hover:bg-secondary/70",
        ghost:
          "hover:bg-muted text-foreground/80 hover:text-foreground",
        destructive:
          "bg-transparent text-destructive border-destructive/40 hover:bg-destructive/8",
        link: "text-primary underline-offset-4 hover:underline border-transparent",
      },
      size: {
        default: "h-8 gap-1.5 px-4 text-[0.8125rem] tracking-wide",
        xs: "h-6 gap-1 px-2.5 text-xs",
        sm: "h-7 gap-1 px-3 text-[0.8rem]",
        lg: "h-10 gap-2 px-5 text-[0.875rem] tracking-wide",
        icon: "size-8",
        "icon-xs": "size-6",
        "icon-sm": "size-7",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin", className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

interface ButtonProps extends ButtonPrimitive.Props, VariantProps<typeof buttonVariants> {
  loading?: boolean
}

function Button({
  className,
  variant = "default",
  size = "default",
  loading,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <ButtonPrimitive
      data-slot="button"
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {loading && <Spinner className="size-3.5 shrink-0" />}
      {children}
    </ButtonPrimitive>
  )
}

export { Button, buttonVariants }
