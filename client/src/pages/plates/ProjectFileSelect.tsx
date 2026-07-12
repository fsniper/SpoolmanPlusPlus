import { UploadOutlined } from "@ant-design/icons";
import { Button, message, Select, Space, Upload } from "antd";
import { useEffect, useState } from "react";
import { getAPIURL } from "../../utils/url";
import { IProjectFile } from "../projects/ProjectFiles";

interface ProjectFileSelectProps {
  projectId?: number;
  value?: number;
  onChange?: (value: number) => void;
}

export const ProjectFileSelect = ({ projectId, value, onChange }: ProjectFileSelectProps) => {
  const [files, setFiles] = useState<IProjectFile[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId) {
      setFiles([]);
      return;
    }

    const fetchFiles = async () => {
      setLoading(true);
      try {
        const response = await fetch(`${getAPIURL()}/project/${projectId}/file`);
        if (response.ok) {
          const data = await response.json();
          setFiles(data);
        }
      } catch (err) {
        console.error("Failed to fetch project files", err);
      } finally {
        setLoading(false);
      }
    };

    fetchFiles();
  }, [projectId]);

  const uploadProps = {
    name: "file",
    action: projectId ? `${getAPIURL()}/project/${projectId}/file` : "",
    showUploadList: false,
    onChange(info: any) {
      if (info.file.status === "done") {
        message.success(`${info.file.name} file uploaded successfully`);
        const newFile = info.file.response;
        setFiles((prev) => [...prev, newFile]);
        if (onChange) {
          onChange(newFile.id);
        }
      } else if (info.file.status === "error") {
        message.error(`${info.file.name} file upload failed.`);
      }
    },
  };

  return (
    <Space style={{ width: "100%" }}>
      <Select
        style={{ minWidth: 250 }}
        placeholder="Select a project file"
        value={value}
        onChange={onChange}
        loading={loading}
        disabled={!projectId}
        allowClear
      >
        {files.map((f) => (
          <Select.Option key={f.id} value={f.id}>
            {f.name}
          </Select.Option>
        ))}
      </Select>
      <Upload {...uploadProps}>
        <Button icon={<UploadOutlined />} disabled={!projectId}>
          Upload New
        </Button>
      </Upload>
    </Space>
  );
};
