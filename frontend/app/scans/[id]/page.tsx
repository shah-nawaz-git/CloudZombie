import { ScanDetail } from "@/components/ScanDetail";
export default async function ScanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ScanDetail id={id} />;
}
