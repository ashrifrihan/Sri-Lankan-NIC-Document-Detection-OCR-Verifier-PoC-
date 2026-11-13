declare module 'lucide-react' {
  import * as React from 'react';

  export interface LucideProps extends React.SVGProps<SVGSVGElement> {
    size?: string | number;
    color?: string;
    strokeWidth?: string | number;
  }

  export type LucideIcon = React.ForwardRefExoticComponent<
    LucideProps & React.RefAttributes<SVGSVGElement>
  >;

  export const Shield: LucideIcon;
  export const UploadCloud: LucideIcon;
  export const FileCheck: LucideIcon;
  export const AlertTriangle: LucideIcon;
  export const RotateCcw: LucideIcon;
  export const Sparkles: LucideIcon;
  export const CheckCircle: LucideIcon;
  export const CheckCircle2: LucideIcon;
  export const ExternalLink: LucideIcon;
  export const Laptop: LucideIcon;
  export const Image: LucideIcon;
  export const Trash2: LucideIcon;
  export const User: LucideIcon;
  export const CreditCard: LucideIcon;
  export const Calendar: LucideIcon;
  export const AlertCircle: LucideIcon;
  export const XCircle: LucideIcon;
  export const HelpCircle: LucideIcon;
  export const FileText: LucideIcon;
  export const ShieldAlert: LucideIcon;
  export const ShieldCheck: LucideIcon;
  export const UserCheck: LucideIcon;
  export const Info: LucideIcon;
  export const RefreshCw: LucideIcon;
  export const Sun: LucideIcon;
  export const Eye: LucideIcon;
  export const Crop: LucideIcon;
  export const X: LucideIcon;
  export const ArrowRight: LucideIcon;
  export const ClipboardCopy: LucideIcon;
}
