import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "group/badge inline-flex h-[1.25rem] w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-sm border px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-[0.08em] font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-ring/50 [&>svg]:pointer-events-none [&>svg]:size-3",
  {
    variants: {
      variant: {
        default:
          "bg-primary/10 text-primary border-primary/25 [a]:hover:bg-primary/15",
        secondary:
          "bg-secondary text-secondary-foreground border-border [a]:hover:bg-secondary/70",
        destructive:
          "bg-destructive/8 text-destructive border-destructive/25 [a]:hover:bg-destructive/15",
        outline:
          "border-border text-foreground/70 bg-transparent [a]:hover:bg-muted",
        ghost:
          "border-transparent text-muted-foreground bg-muted [a]:hover:bg-muted/70",
        link: "border-transparent text-primary underline-offset-4 hover:underline",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
