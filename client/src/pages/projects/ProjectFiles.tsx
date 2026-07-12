import { Button, Form, Input, Modal, Select, Space, Table, Upload, message, Tooltip, Popconfirm } from "antd";
import { DownloadOutlined, DeleteOutlined, LinkOutlined, UploadOutlined, EyeOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { getAPIURL } from "../../utils/url";
import { useSelect } from "@refinedev/antd";
import { IPlate } from "../plates/model";
import { STLPreviewModal } from "../plates/STLPreviewModal";

export interface IProjectFile {
  id: number;
  project_id: number;
  plate_id?: number;
  name: string;
  file_path?: string;
  size?: number;
  registered: string;
}

interface ProjectFilesProps {
  projectId: number;
}

export const ProjectFiles = ({ projectId }: ProjectFilesProps) => {
  const [files, setFiles] = useState<IProjectFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [isLinkModalVisible, setIsLinkModalVisible] = useState(false);
  const [previewFile, setPreviewFile] = useState<IProjectFile | null>(null);
  const [linkForm] = Form.useForm();
  
  const { selectProps: plateSelectProps } = useSelect<IPlate>({
    resource: "plate",
    optionLabel: "name",
    optionValue: "id",
    filters: [
      {
        field: "project_id",
        operator: "eq",
        value: projectId,
      },
    ],
  });

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${getAPIURL()}/project/${projectId}/file`);
      if (!response.ok) throw new Error("Failed to fetch files");
      const data = await response.json();
      setFiles(data);
    } catch (err) {
      message.error("Failed to load project files");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleDelete = async (fileId: number) => {
    try {
      const response = await fetch(`${getAPIURL()}/project/${projectId}/file/${fileId}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Failed to delete file");
      message.success("File deleted");
      fetchFiles();
    } catch (err) {
      message.error("Failed to delete file");
    }
  };

  const handleDownload = (fileId: number, name: string) => {
    window.open(`${getAPIURL()}/project/${projectId}/file/${fileId}/download`);
  };

  const handleLinkSubmit = async () => {
    try {
      const values = await linkForm.validateFields();
      const formData = new FormData();
      formData.append("plate_id", values.plate_id);
      if (values.name) {
        formData.append("name", values.name);
      }

      const response = await fetch(`${getAPIURL()}/project/${projectId}/file/link`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Failed to link file");
      message.success("Plate linked as file");
      setIsLinkModalVisible(false);
      linkForm.resetFields();
      fetchFiles();
    } catch (err) {
      message.error("Failed to link plate");
    }
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "Size",
      dataIndex: "size",
      key: "size",
      render: (size: number) => size ? `${(size / 1024 / 1024).toFixed(2)} MB` : "-",
    },
    {
      title: "Type",
      key: "type",
      render: (_: any, record: IProjectFile) => record.plate_id ? "Linked Plate" : "Uploaded File",
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, record: IProjectFile) => {
        const isPreviewable = record.name.toLowerCase().endsWith(".stl") || record.name.toLowerCase().endsWith(".gcode");
        return (
          <Space>
            {isPreviewable && (
              <Tooltip title="Preview 3D">
                <Button
                  icon={<EyeOutlined />}
                  onClick={() => setPreviewFile(record)}
                />
              </Tooltip>
            )}
            <Tooltip title="Download">
              <Button
                icon={<DownloadOutlined />}
                onClick={() => handleDownload(record.id, record.name)}
                disabled={!!record.plate_id} // Currently we don't have download for linked plate files directly unless it's an uploaded plate
              />
            </Tooltip>
            <Popconfirm title="Are you sure you want to delete this file?" onConfirm={() => handleDelete(record.id)}>
              <Button danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  const uploadProps = {
    name: "file",
    action: `${getAPIURL()}/project/${projectId}/file`,
    showUploadList: false,
    onChange(info: any) {
      if (info.file.status === "done") {
        message.success(`${info.file.name} file uploaded successfully`);
        fetchFiles();
      } else if (info.file.status === "error") {
        message.error(`${info.file.name} file upload failed.`);
      }
    },
  };

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3>Project Files</h3>
        <Space>
          <Button icon={<LinkOutlined />} onClick={() => setIsLinkModalVisible(true)}>
            Link Plate
          </Button>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />} type="primary">
              Upload File
            </Button>
          </Upload>
        </Space>
      </div>

      <Table
        dataSource={files}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
      />

      <STLPreviewModal 
        plate={previewFile ? {
          id: 0,
          project_id: projectId,
          project_file_id: previewFile.id,
          name: previewFile.name,
          file_path: previewFile.name,
          registered: "",
        } : null} 
        open={!!previewFile} 
        onClose={() => setPreviewFile(null)} 
      />

      <Modal
        title="Link Plate as File"
        open={isLinkModalVisible}
        onOk={handleLinkSubmit}
        onCancel={() => setIsLinkModalVisible(false)}
      >
        <Form form={linkForm} layout="vertical">
          <Form.Item
            name="plate_id"
            label="Select Plate"
            rules={[{ required: true, message: "Please select a plate" }]}
          >
            <Select {...plateSelectProps} placeholder="Select a plate from this project" />
          </Form.Item>
          <Form.Item name="name" label="Display Name (optional)">
            <Input placeholder="Leave blank to use plate name" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
