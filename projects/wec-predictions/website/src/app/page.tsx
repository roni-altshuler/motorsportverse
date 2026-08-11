import HomePage from "@/components/HomePage";
import { getCalibrationSummary, getWecData } from "@/lib/wecData";

export default function Page() {
  const data = getWecData();
  const calibration = getCalibrationSummary();
  return <HomePage data={data} calibration={calibration} />;
}
