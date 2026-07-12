import { Modal } from "antd";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { GCodeLoader } from "three/examples/jsm/loaders/GCodeLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { getAPIURL } from "../../utils/url";
import { IPlate } from "./model";

interface STLPreviewModalProps {
  plate: IPlate | null;
  open: boolean;
  onClose: () => void;
}

const Viewer = ({ url, isGCode }: { url: string, isGCode: boolean }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x222222);

    const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    
    // Clear any existing canvases (useful for React 18 Strict Mode or HMR)
    if (mountRef.current) {
      mountRef.current.innerHTML = "";
      mountRef.current.appendChild(renderer.domElement);
    }

    const handleResize = () => {
      if (!mountRef.current) return;
      const width = mountRef.current.clientWidth;
      const height = mountRef.current.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    handleResize();

    const resizeObserver = new ResizeObserver(() => handleResize());
    resizeObserver.observe(mountRef.current);

    const controls = new OrbitControls(camera, renderer.domElement);
    
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(1, 1, 1);
    scene.add(directionalLight);

    if (isGCode) {
      const loader = new GCodeLoader();
      loader.load(
        url,
        (object: THREE.Object3D) => {
          const bbox = new THREE.Box3().setFromObject(object);
          const center = new THREE.Vector3();
          bbox.getCenter(center);
          object.position.sub(center);
          
          object.rotation.x = -Math.PI / 2;

          const size = new THREE.Vector3();
          bbox.getSize(size);
          const maxDim = Math.max(size.x, size.y, size.z);
          
          camera.position.z = maxDim * 1.5;
          camera.position.y = maxDim * 1.5;
          camera.far = Math.max(1000, maxDim * 10);
          camera.updateProjectionMatrix();

          controls.target.set(0, 0, 0);
          controls.update();
          
          scene.add(object);
        },
        undefined,
        (err: unknown) => {
          console.error(err);
          setError("Failed to load GCode file.");
        }
      );
    } else {
      const loader = new STLLoader();
      loader.load(
        url,
        (geometry: THREE.BufferGeometry) => {
          geometry.computeVertexNormals();
          const material = new THREE.MeshPhongMaterial({ color: 0x1677ff, specular: 0x111111, shininess: 200 });
          const mesh = new THREE.Mesh(geometry, material);
          
          geometry.computeBoundingBox();
          const bbox = geometry.boundingBox!;
          const center = new THREE.Vector3();
          bbox.getCenter(center);
          mesh.position.sub(center); // Center the mesh
          
          // Rotate so Z is up (common for STL files)
          mesh.rotation.x = -Math.PI / 2;

          const size = new THREE.Vector3();
          bbox.getSize(size);
          const maxDim = Math.max(size.x, size.y, size.z);
          
          camera.position.z = maxDim * 1.5;
          camera.position.y = maxDim * 1.5; // Look down slightly
          camera.far = Math.max(1000, maxDim * 10);
          camera.updateProjectionMatrix();

          controls.target.set(0, 0, 0);
          controls.update();
          
          scene.add(mesh);
        },
        undefined,
        (err: unknown) => {
          console.error(err);
          setError("Failed to load STL file.");
        }
      );
    }

    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [url]);

  if (error) return <div style={{ color: "red", padding: "1rem" }}>{error}</div>;
  return <div ref={mountRef} style={{ width: "100%", height: "100%" }} />;
};

export const STLPreviewModal = ({ plate, open, onClose }: STLPreviewModalProps) => {
  if (!plate || !plate.project_file_id) return null;

  const fileUrl = `${getAPIURL()}/project/${plate.project_id}/file/${plate.project_file_id}/download`;
  const isStl = plate.file_path?.toLowerCase().endsWith(".stl");
  const isGCode = plate.file_path?.toLowerCase().endsWith(".gcode");

  if (!isStl && !isGCode) return null;

  return (
    <Modal
      title={`Preview: ${plate.name}`}
      open={open}
      onCancel={onClose}
      footer={null}
      width={800}
      centered
      destroyOnClose
      bodyStyle={{ padding: 0, overflow: "hidden", borderRadius: "0 0 8px 8px" }}
    >
      <div style={{ height: "450px", width: "100%", position: "relative" }}>
        {open && <Viewer url={fileUrl} isGCode={!!isGCode} />}
      </div>
    </Modal>
  );
};
