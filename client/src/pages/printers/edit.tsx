import { Edit, useForm } from "@refinedev/antd";
import { HttpError } from "@refinedev/core";
import { Alert, DatePicker, Form, Input, message } from "antd";
import TextArea from "antd/es/input/TextArea";
import dayjs from "dayjs";
import { useState } from "react";
import { IPrinter } from "./model";

export const PrinterEdit = () => {
  const [messageApi, contextHolder] = message.useMessage();
  const [hasChanged, setHasChanged] = useState(false);

  const { formProps, saveButtonProps } = useForm<IPrinter, HttpError, IPrinter, IPrinter>({
    liveMode: "manual",
    onLiveEvent() {
      messageApi.warning("This printer has been updated since you opened the form.");
      setHasChanged(true);
    },
  });

  return (
    <Edit saveButtonProps={saveButtonProps}>
      {contextHolder}
      <Form {...formProps} layout="vertical">
        <Form.Item label="ID" name={["id"]}>
          <Input readOnly disabled />
        </Form.Item>
        <Form.Item label="Registered" name={["registered"]} getValueProps={(v) => ({ value: v ? dayjs(v) : undefined })}>
          <DatePicker disabled showTime format="YYYY-MM-DD HH:mm:ss" />
        </Form.Item>
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
      {hasChanged && <Alert description="This printer has been updated since you opened the form." type="warning" showIcon />}
    </Edit>
  );
};

export default PrinterEdit;
