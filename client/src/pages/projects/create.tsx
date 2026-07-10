import { Create, useForm } from "@refinedev/antd";
import { HttpError, IResourceComponentsProps } from "@refinedev/core";
import { Button, Form, Input } from "antd";
import TextArea from "antd/es/input/TextArea";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { IProject } from "./model";

dayjs.extend(utc);

interface CreateOrCloneProps {
  mode: "create" | "clone";
}

export const ProjectCreate = (props: IResourceComponentsProps & CreateOrCloneProps) => {
  const { form, formProps, formLoading, onFinish, redirect } = useForm<IProject, HttpError, IProject, IProject>();

  if (!formProps.initialValues) {
    formProps.initialValues = {};
  }

  const handleSubmit = async (redirectTo: "list" | "edit" | "create") => {
    const values = await form.validateFields();
    await onFinish(values);
    redirect(redirectTo, (values as IProject).id);
  };

  return (
    <Create
      title={props.mode === "create" ? "Create Project" : "Clone Project"}
      isLoading={formLoading}
      footerButtons={() => (
        <>
          <Button type="primary" onClick={() => handleSubmit("list")}>
            Save
          </Button>
          <Button type="primary" onClick={() => handleSubmit("create")}>
            Save and Add Another
          </Button>
        </>
      )}
    >
      <Form {...formProps} layout="vertical">
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
    </Create>
  );
};

export default ProjectCreate;
