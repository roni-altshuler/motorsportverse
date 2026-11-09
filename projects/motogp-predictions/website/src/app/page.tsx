import PublicationHoldNotice from "@/components/PublicationHoldNotice";
import { getPublicationHold } from "@/lib/publication";
import HomePage from "@/components/HomePage";

// Server component: HomePage reads the build-time MotoGP dataset via getMotogpData()
// and renders the ported home + marketing sections.
export default function Page() {
  const publicationHold = getPublicationHold();
  if (publicationHold) return <PublicationHoldNotice hold={publicationHold} />;
  return <HomePage />;
}
