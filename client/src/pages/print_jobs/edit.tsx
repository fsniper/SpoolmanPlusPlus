import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { Edit, useForm, useSelect } from "@refinedev/antd";
import { HttpError } from "@refinedev/core";
import { Button, DatePicker, Form, Input, InputNumber, Select, Space } from "antd";
import TextArea from "antd/es/input/TextArea";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { IPlate } from "../plates/model";
import { IPrinter } from "../printers/model";
import { ISpool } from "../spools/model";
import { IPrintJob } from "./model";

dayjs.extend(utc);

export const PrintJobEdit = () => {
  const { formProps, saveButtonProps } = useForm<IPrintJob, HttpError, IPrintJob, IPrintJob>({
    liveMode: "manual",
  });

  const { selectProps: plateSelectProps } = useSelect<IPlate>({
    resource: "plate",
    optionLabel: "name",
    optionValue: "id",
  });

  const { selectProps: spoolSelectProps } = useSelect<ISpool>({
    resource: "spool",
    optionLabel: (item) =>
      `#${item.id} — ${item.filament?.name ?? "Unknown"} (${item.remaining_weight != null ? item.remaining_weight.toFixed(0) + "g" : "?g"} left)`,
    optionValue: "id",
  });

  const { selectProps: printerSelectProps } = useSelect<IPrinter>({
    resource: "printer",
    optionLabel: (item) => item.model ? `${item.name} (${item.model})` : item.name,
    optionValue: "id",
  });

  // Convert ISO datetime strings to dayjs objects for DatePicker fields
  const originalOnFinish = formProps.onFinish;
  formProps.onFinish = (allValues: IPrintJob) => {
    if (allValues !== undefined && allValues !== null) {
      const payload = {
        ...allValues,
        start_time: allValues.start_time
          ? (allValues.start_time as unknown as dayjs.Dayjs).toISOString?.() ?? allValues.start_time
          : undefined,
        end_time: allValues.end_time
          ? (allValues.end_time as unknown as dayjs.Dayjs).toISOString?.() ?? allValues.end_time
          : undefined,
      };
      originalOnFinish?.(payload);
    }
  };

  return (
    <Edit title="Edit Print Job" saveButtonProps={saveButtonProps}>
      <Form {...formProps} layout="vertical">
        <Form.Item label="ID" name={["id"]} rules={[{ required: true }]}>
          <Input readOnly disabled />
        </Form.Item>

        <Form.Item
          label="Registered"
          name={["registered"]}
          getValueProps={(value) => ({
            value: value ? dayjs(value) : undefined,
          })}
        >
          <DatePicker disabled showTime format="YYYY-MM-DD HH:mm:ss" style={{ width: "100%" }} />
        </Form.Item>

        <Form.Item
          label="Plate"
          name={["plate_id"]}
          rules={[{ required: true, message: "Please select a plate" }]}
        >
          <Select
            {...plateSelectProps}
            showSearch
            filterOption={(input, option) =>
              String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())
            }
            placeholder="Select a plate"
          />
        </Form.Item>

        <Form.Item label="Status" name={["status"]} rules={[{ required: false }]}>
          <Select
            options={[
              { label: "Queued", value: "queued" },
              { label: "In Progress", value: "in_progress" },
              { label: "Successful", value: "successful" },
              { label: "Failed", value: "failed" },
              { label: "Canceled", value: "canceled" },
            ]}
            allowClear
          />
        </Form.Item>

        <Form.Item label="Printer" name={["printer_id"]}>
          <Select
            {...printerSelectProps}
            showSearch
            allowClear
            filterOption={(input, option) =>
              String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())
            }
            placeholder="Select a printer"
          />
        </Form.Item>

        <Form.Item
          label="Start Time"
          name={["start_time"]}
          rules={[{ required: false }]}
          getValueProps={(value) => ({
            value: value ? dayjs(value) : undefined,
          })}
        >
          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" style={{ width: "100%" }} />
        </Form.Item>

        <Form.Item
          label="End Time"
          name={["end_time"]}
          rules={[{ required: false }]}
          getValueProps={(value) => ({
            value: value ? dayjs(value) : undefined,
          })}
        >
          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" style={{ width: "100%" }} />
        </Form.Item>

        <Form.Item label="Comment" name={["comment"]} rules={[{ required: false }]}>
          <TextArea maxLength={1024} rows={3} />
        </Form.Item>

        <Form.Item label="Spool Usages">
          <Form.List name="spool_usages">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }) => (
                  <Space key={key} style={{ display: "flex", marginBottom: 8, alignItems: "baseline" }} align="baseline">
                    <Form.Item
                      {...restField}
                      name={[name, "spool_id"]}
                      label="Spool"
                      rules={[{ required: true, message: "Please select a spool" }]}
                      style={{ minWidth: 300 }}
                    >
                      <Select
                        {...spoolSelectProps}
                        showSearch
                        filterOption={(input, option) =>
                          String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())
                        }
                        placeholder="Select a spool"
                      />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, "weight_used"]}
                      label="Weight Used (g)"
                      rules={[{ required: true, type: "number", min: 0, message: "Weight used is required" }]}
                    >
                      <InputNumber min={0} step={0.1} precision={1} placeholder="0.0" addonAfter="g" />
                    </Form.Item>
                    <MinusCircleOutlined
                      style={{ color: "#ff4d4f", cursor: "pointer", fontSize: 16 }}
                      onClick={() => remove(name)}
                    />
                  </Space>
                ))}
                <Form.Item>
                  <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />} style={{ width: "100%" }}>
                    Add Spool Usage
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>
        </Form.Item>
      </Form>
    </Edit>
  );
};

export default PrintJobEdit;
