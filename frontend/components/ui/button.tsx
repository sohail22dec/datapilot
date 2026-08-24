import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FEC50B]/50 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-[#FEC50B] text-[#111827] font-semibold hover:bg-[#F4B900] active:scale-[0.99] shadow-xs",
        primary:
          "bg-[#FEC50B] text-[#111827] font-semibold hover:bg-[#F4B900] active:scale-[0.99] shadow-xs",
        secondary:
          "bg-[#242834] text-[#F1F5F9] hover:bg-[#2E3444] border border-[#323849]",
        ghost:
          "text-[#94A3B8] hover:text-white hover:bg-[#282E3A]",
        outline:
          "border border-[#2E3444] bg-transparent hover:bg-[#282E3A] text-[#CBD5E1] hover:text-white",
        destructive:
          "bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30",
        link: "text-[#FEC50B] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-12 rounded-xl px-6 text-base",
        icon: "h-9 w-9 p-0",
        iconSm: "h-8 w-8 p-0 rounded-lg",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
