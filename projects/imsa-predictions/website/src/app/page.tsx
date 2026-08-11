import HomePage from "@/components/HomePage";
import { getCalibrationSummary, getImsaData } from "@/lib/imsaData";

export default function Page() {
  const data = getImsaData();
  const calibration = getCalibrationSummary();
  return <HomePage data={data} calibration={calibration} />;
}
