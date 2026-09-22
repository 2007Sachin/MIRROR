import { Loader } from "@/components/loader";
import { loading } from "@/lib/copy";

export default function AppLoading() {
  return (
    <main id="main-content" className="shell">
      <Loader page label={loading.app.label} note={loading.app.note} />
    </main>
  );
}
