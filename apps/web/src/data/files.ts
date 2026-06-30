export interface FileNode {
  id: string;
  name: string;
  type: "file" | "folder";
  children?: FileNode[];
  extension?: string;
}

/* courseFiles 已由 GET /api/courses/{id}/files/ 替代 */
