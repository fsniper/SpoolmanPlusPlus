import { Create, useForm, useSelect } from "@refinedev/antd";
import { HttpError, IResourceComponentsProps } from "@refinedev/core";
import { Button, Form, Input, InputNumber, Select } from "antd";
import TextArea from "antd/es/input/TextArea";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { useSearchParams } from "react-router";
import { IProject } from "../projects/model";
import { IPlate } from "./model";

dayjs.extend(utc);

interface CreateOrCloneProps {
  mode: "create" | "clone";
}

export const PlateCreate = (props: IResourceComponentsProps & CreateOrCloneProps) => {
  const [searchParams] = useSearchParams();
  const projectIdFromUrl = searchParams.get("project_id") ? Number(searchParams.get("project_id")) : undefined;

  const { form, formProps, formLoading, onFinish, redirect } = useForm<IPlate, HttpError, IPlate, IPlate>();

  const { selectProps: projectSelectProps } = useSelect<IProject>({
    resource: "project",
    optionLabel: "name",
    optionValue: "id",
    defaultValue: projectIdFromUrl,
  });

  if (!formProps.initialValues) {
    formProps.initialValues = {};
  }
  if (projectIdFromUrl && !formProps.initialValues.project_id) {
    formProps.initialValues.project_id = projectIdFromUrl;
  }

  const handleSubmit = async (redirectTo: "list" | "edit" | "create") => {
    const values = await form.validateFields();
    await onFinish(values);
    redirect(redirectTo, (values as IPlate).id);
  };

  return (
    <Create
      title={props.mode === "create" ? "Create Plate" : "Clone Plate"}
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
        <Form.Item label="File Path" name={["file_path"]}>
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
    </Create>
  );
};

export default PlateCreate;
