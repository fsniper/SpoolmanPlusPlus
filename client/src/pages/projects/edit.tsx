import { Edit, useForm } from "@refinedev/antd";
import { HttpError } from "@refinedev/core";
import { Alert, DatePicker, Form, Input, message } from "antd";
import TextArea from "antd/es/input/TextArea";
import dayjs from "dayjs";
import { useState } from "react";
import { IProject } from "./model";
import { ProjectFiles } from "./ProjectFiles";

export const ProjectEdit = () => {
  const [messageApi, contextHolder] = message.useMessage();
  const [hasChanged, setHasChanged] = useState(false);

  const { formProps, saveButtonProps } = useForm<IProject, HttpError, IProject, IProject>({
    liveMode: "manual",
    onLiveEvent() {
      messageApi.warning("This project has been updated since you opened the form.");
      setHasChanged(true);
    },
  });

  return (
    <Edit saveButtonProps={saveButtonProps}>
      {contextHolder}
      <Form {...formProps} layout="vertical">
        <Form.Item
          label="ID"
          name={["id"]}
          rules={[
            {
              required: true,
            },
          ]}
        >
          <Input readOnly disabled />
        </Form.Item>
        <Form.Item
          label="Registered"
          name={["registered"]}
          rules={[
            {
              required: true,
            },
          ]}
          getValueProps={(value) => ({
            value: value ? dayjs(value) : undefined,
          })}
        >
          <DatePicker disabled showTime format="YYYY-MM-DD HH:mm:ss" />
        </Form.Item>
        <Form.Item
          label="Name"
          name={["name"]}
          rules={[
            {
              required: true,
            },
          ]}
        >
          <Input maxLength={64} />
        </Form.Item>
        <Form.Item
          label="Description"
          name={["description"]}
          rules={[
            {
              required: false,
            },
          ]}
        >
          <TextArea maxLength={1024} />
        </Form.Item>
        <Form.Item
          label="Link"
          name={["link"]}
          rules={[
            {
              required: false,
              type: "url",
            },
          ]}
        >
          <Input maxLength={256} placeholder="https://..." />
        </Form.Item>
      </Form>
      {hasChanged && <Alert description="This project has been updated since you opened the form." type="warning" showIcon />}
      {formProps.initialValues?.id && (
        <ProjectFiles projectId={formProps.initialValues.id} />
      )}
    </Edit>
  );
};

export default ProjectEdit;
