import { ArrowLeft } from "lucide-react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { ResourceReader } from "../components/document-reader/ResourceReader";
import { resolveReaderResourceId } from "../services/resourceCompat";

export function LibraryReaderPage() {
  const { sourceVersionId } = useParams();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("returnTo")?.trim() || "/library";
  const resourceId = resolveReaderResourceId({ sourceVersionId: sourceVersionId ?? undefined });

  if (!resourceId) {
    return <Navigate replace to="/library" />;
  }

  const backPath = returnTo.startsWith("/") ? returnTo : "/library";

  return (
    <AppShell>
      <div className="library-reader-page">
        <header className="library-reader-header">
          <Link className="library-reader-back" to={backPath}>
            <ArrowLeft size={16} />
            返回
          </Link>
          <h1>资料预览</h1>
        </header>
        <ResourceReader sourceVersionId={resourceId} />
      </div>
    </AppShell>
  );
}
