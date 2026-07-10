import { Create, useForm } from "@refinedev/antd";
import { HttpError, IResourceComponentsProps } from "@refinedev/core";
import { Button, Form, Input } from "antd";
import TextArea from "antd/es/input/TextArea";
import { IPrinter } from "./model";

interface CreateOrCloneProps {
  mode: "create" | "clone";
}

export const PrinterCreate = (props: IResourceComponentsProps & CreateOrCloneProps) => {
  const { form, formProps, formLoading, onFinish, redirect } = useForm<IPrinter, HttpError, IPrinter, IPrinter>();

  const handleSubmit = async (redirectTo: "list" | "edit" | "create") => {
    const values = await form.validateFields();
    await onFinish(values);
    redirect(redirectTo, (values as IPrinter).id);
  };

  return (
    <Create
      title={props.mode === "create" ? "Create Printer" : "Clone Printer"}
      isLoading={formLoading}
      footerButtons={() => (
        <>
          <Button type="primary" onClick={() => handleSubmit("list")}>Save</Button>
          <Button type="primary" onClick={() => handleSubmit("create")}>Save and Add Another</Button>
        </>
      )}
    >
      <Form {...formProps} layout="vertical">
        <Form.Item label="Name" name={["name"]} rules={[{ required: true }]}>
          <Input maxLength={256} />
        </Form.Item>
        <Form.Item label="Model" name={["model"]}>
          <Input maxLength={256} placeholder="e.g. Bambu X1C" />
        </Form.Item>
        <Form.Item label="Location" name={["location"]}>
          <Input maxLength={256} placeholder="e.g. Workshop" />
        </Form.Item>
        <Form.Item label="Comment" name={["comment"]}>
          <TextArea maxLength={1024} />
        </Form.Item>
      </Form>
    </Create>
  );
};

export default PrinterCreate;
