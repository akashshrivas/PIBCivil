import { notFound } from "next/navigation";
import { getArticle } from "@/lib/api";
import ArticleDetailContent from "@/components/ArticleDetailContent";
import Modal from "@/components/Modal";

export const dynamic = "force-dynamic";

interface ArticleModalProps {
  params: Promise<{ id: string }>;
}

export default async function ArticleModal({ params }: ArticleModalProps) {
  const { id } = await params;

  let article;
  try {
    article = await getArticle(id);
  } catch {
    notFound();
  }

  return (
    <Modal>
      <ArticleDetailContent article={article} />
    </Modal>
  );
}
