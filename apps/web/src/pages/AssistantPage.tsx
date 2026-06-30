import { AppShell } from "../components/AppShell";
import { AiChatPanel } from "../features/assistant/AiChatPanel";

export function AssistantPage() {
  return (
    <AppShell>
      <AiChatPanel mode="page" />
    </AppShell>
  );
}
