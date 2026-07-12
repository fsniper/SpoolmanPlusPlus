import { Edit, useForm, useSelect } from "@refinedev/antd";
import { HttpError } from "@refinedev/core";
import { Alert, DatePicker, Form, Input, InputNumber, Select, message } from "antd";
import TextArea from "antd/es/input/TextArea";
import dayjs from "dayjs";
import { useState } from "react";
import { IProject } from "../projects/model";
import { IPlate } from "./model";
import { ProjectFileSelect } from "./ProjectFileSelect";

export const PlateEdit = () => {
  const [messageApi, contextHolder] = message.useMessage();
  const [hasChanged, setHasChanged] = useState(false);

  const { formProps, saveButtonProps } = useForm<IPlate, HttpError, IPlate, IPlate>({
    liveMode: "manual",
    onLiveEvent() {
      messageApi.warning("This plate has been updated since you opened the form.");
      setHasChanged(true);
    },
  });
  
  const selectedProjectId = Form.useWatch("project_id", formProps.form);

  const { selectProps: projectSelectProps } = useSelect<IProject>({
    resource: "project",
    optionLabel: "name",
    optionValue: "id",
    defaultValue: formProps.initialValues?.project_id,
  });

  return (
    <Edit saveButtonProps={saveButtonProps}>
      {contextHolder}
      <Form {...formProps} layout="vertical">
        <Form.Item label="ID" name={["id"]}>
          <Input readOnly disabled />
        </Form.Item>
        <Form.Item
          label="Registered"
          name={["registered"]}
          getValueProps={(value) => ({ value: value ? dayjs(value) : undefined })}
        >
          <DatePicker disabled showTime format="YYYY-MM-DD HH:mm:ss" />
        </Form.Item>
        <Form.Item
          label="Project"
          name={["project_id"]}
          rules={[{ required: true, message: "Please select a project" }]}
        >
          <Select
            {...projectSelectProps}
            showSearch
            filterOption={(input, option) =>
              String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())
            }
            placeholder="Select a project"
          />
        </Form.Item>
        <Form.Item label="Name" name={["name"]} rules={[{ required: true }]}>
          <Input maxLength={256} />
        </Form.Item>
        <Form.Item label="Project File" name={["project_file_id"]} help="Link this plate to an uploaded file or upload a new one.">
          <ProjectFileSelect projectId={selectedProjectId || formProps.initialValues?.project_id} />
        </Form.Item>
        <Form.Item label="Raw File Path" name={["file_path"]} help="Alternative raw file path for the plate.">
          <Input maxLength={1024} placeholder="/path/to/file.gcode" />
        </Form.Item>
        <Form.Item
          label="Estimated Weight"
          name={["estimated_weight"]}
          rules={[{ type: "number", min: 0 }]}
        >
          <InputNumber addonAfter="g" precision={1} min={0} />
        </Form.Item>
        <Form.Item
          label="Estimated Time (seconds)"
          name={["estimated_time"]}
          rules={[{ type: "number", min: 0 }]}
        >
          <InputNumber addonAfter="s" precision={0} min={0} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item label="Comment" name={["comment"]}>
          <TextArea maxLength={1024} />
        </Form.Item>
      </Form>
      {hasChanged && <Alert description="This plate has been updated since you opened the form." type="warning" showIcon />}
    </Edit>
  );
};

export default PlateEdit;
