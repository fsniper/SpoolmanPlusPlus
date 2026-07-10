import { DeleteOutlined, EditOutlined, EyeOutlined, FilterOutlined } from "@ant-design/icons";
import { List, useTable } from "@refinedev/antd";
import { useDelete, useInvalidate, useNavigation, useTranslate } from "@refinedev/core";
import { Button, Modal, Table, Tag } from "antd";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router";
import { ActionsColumn, DateColumn, SortedColumn } from "../../components/column";
import { useLiveify } from "../../components/liveify";
import { removeUndefined } from "../../utils/filtering";
import { TableState, useInitialTableState, useStoreInitialState } from "../../utils/saveload";
import { IPrintJob } from "./model";

dayjs.extend(utc);

const { confirm } = Modal;

const namespace = "printJobList-v1";

const allColumns: (keyof IPrintJob & string)[] = [
  "id",
  "plate_id",
  "status",
  "printer_id",
  "start_time",
  "end_time",
  "comment",
];

const statusTagColor: Record<string, string> = {
  queued: "orange",
  successful: "green",
  failed: "red",
  in_progress: "blue",
  canceled: "gray",
};

export const PrintJobList = () => {
  const t = useTranslate();
  const invalidate = useInvalidate();
  const navigate = useNavigate();
  const { mutate: deleteOne } = useDelete();

  // Load initial state
  const initialState = useInitialTableState(namespace);

  // Fetch data from the API
  const { tableProps, sorters, setSorters, filters, setFilters, currentPage, pageSize, setCurrentPage } =
    useTable<IPrintJob>({
      syncWithLocation: false,
      pagination: {
        mode: "server",
        currentPage: initialState.pagination.currentPage,
        pageSize: initialState.pagination.pageSize,
      },
      sorters: {
        mode: "server",
        initial: initialState.sorters,
      },
      filters: {
        mode: "server",
        initial: initialState.filters,
      },
      liveMode: "manual",
      onLiveEvent(event) {
        if (event.type === "created" || event.type === "deleted") {
          invalidate({
            resource: "print_job",
            invalidates: ["list"],
          });
        }
      },
    });

  // Store state in local storage
  const tableState: TableState = {
    sorters,
    filters,
    pagination: { currentPage, pageSize },
    showColumns: allColumns,
  };
  useStoreInitialState(namespace, tableState);

  // Collapse the dataSource to a mutable list
  const queryDataSource: IPrintJob[] = useMemo(() => {
    return (tableProps.dataSource || []).map((record) => ({ ...record }));
  }, [tableProps.dataSource]);
  const dataSource = useLiveify(
    "print_job",
    queryDataSource,
    useCallback((record: IPrintJob) => record, []),
  );

  if (tableProps.pagination) {
    tableProps.pagination.showSizeChanger = true;
  }

  const { editUrl, showUrl } = useNavigation();

  const handleDelete = useCallback(
    (record: IPrintJob) => {
      confirm({
        title: "Delete Print Job",
        content: `Are you sure you want to delete print job #${record.id}?`,
        okText: "Delete",
        okType: "danger",
        cancelText: "Cancel",
        onOk() {
          deleteOne(
            { resource: "print_job", id: record.id },
            {
              onSuccess: () => {
                invalidate({ resource: "print_job", invalidates: ["list"] });
              },
            },
          );
        },
      });
    },
    [deleteOne, invalidate],
  );

  const actions = useCallback(
    (record: IPrintJob) => [
      { name: "Show", icon: <EyeOutlined />, link: showUrl("print_job", record.id) },
      { name: "Edit", icon: <EditOutlined />, link: editUrl("print_job", record.id) },
      { name: "Delete", icon: <DeleteOutlined />, onClick: () => handleDelete(record) },
    ],
    [showUrl, editUrl, handleDelete],
  );

  const commonProps = {
    t,
    navigate,
    actions,
    dataSource,
    tableState,
    sorter: true,
  };

  return (
    <List>
      <Button
        type="default"
        icon={<FilterOutlined />}
        style={{ marginBottom: 16 }}
        onClick={() => {
          setFilters([], "replace");
          setSorters([{ field: "id", order: "asc" }]);
          setCurrentPage(1);
        }}
      >
        Clear Filters
      </Button>
      <Table
        {...tableProps}
        sticky
        tableLayout="auto"
        scroll={{ x: "max-content" }}
        dataSource={dataSource}
        rowKey="id"
        columns={removeUndefined([
          SortedColumn({
            ...commonProps,
            id: "id",
            i18ncat: "print_job",
            title: "ID",
            width: 70,
          }),
          SortedColumn({
            ...commonProps,
            id: "plate_id",
            i18ncat: "print_job",
            title: "Plate ID",
            width: 100,
          }),
          {
            key: "status",
            title: "Status",
            dataIndex: "status",
            width: 130,
            render: (value: string) => {
              const color = statusTagColor[value] ?? "default";
              return (
                <Tag color={color} style={{ textTransform: "capitalize" }}>
                  {value?.replace("_", " ") ?? ""}
                </Tag>
              );
            },
          },
          SortedColumn({
            ...commonProps,
            id: "printer_id",
            i18ncat: "print_job",
            title: "Printer",
          }),
          DateColumn({
            ...commonProps,
            id: "start_time",
            i18ncat: "print_job",
            title: "Start Time",
            width: 180,
          }),
          DateColumn({
            ...commonProps,
            id: "end_time",
            i18ncat: "print_job",
            title: "End Time",
            width: 180,
          }),
          SortedColumn({
            ...commonProps,
            id: "comment",
            i18ncat: "print_job",
            title: "Comment",
          }),
          ActionsColumn<IPrintJob>("Actions", actions),
        ])}
      />
    </List>
  );
};

export default PrintJobList;
