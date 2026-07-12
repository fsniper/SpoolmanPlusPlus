import { Modal } from "antd";
import { Suspense, lazy } from "react";
import { getAPIURL } from "../../utils/url";
import { IPlate } from "./model";

// Lazy load the StlViewer to reduce initial bundle size
const StlViewer = lazy(() => import("react-stl-viewer").then(module => ({ default: module.StlViewer })));

interface STLPreviewModalProps {
  plate: IPlate | null;
  open: boolean;
  onClose: () => void;
}

export const STLPreviewModal = ({ plate, open, onClose }: STLPreviewModalProps) => {
  if (!plate || !plate.project_file_id) {
    return null;
  }

  const fileUrl = `${getAPIURL()}/project/${plate.project_id}/file/${plate.project_file_id}/download`;
  const isStl = plate.file_path?.toLowerCase().endsWith(".stl");

  if (!isStl) {
    return null;
  }

  return (
    <Modal
      title={`Preview: ${plate.name}`}
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      destroyOnClose
    >
      <div style={{ height: "60vh", width: "100%", position: "relative" }}>
        <Suspense fallback={<div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}>Loading 3D Viewer...</div>}>
          <StlViewer
            style={{ top: 0, left: 0, width: "100%", height: "100%" }}
            orbitControls
            shadows
            url={fileUrl}
            modelProps={{ color: "#1677ff" }}
          />
        </Suspense>
      </div>
    </Modal>
  );
};
