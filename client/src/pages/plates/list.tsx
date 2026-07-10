import { EditOutlined, FilterOutlined, PrinterOutlined, PlusSquareOutlined } from "@ant-design/icons";
import { List, useTable } from "@refinedev/antd";
import { useInvalidate, useNavigation, useTranslate } from "@refinedev/core";
import { Button, Table } from "antd";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { useCallback, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import {
  ActionsColumn,
  DateColumn,
  NumberColumn,
  SortedColumn,
} from "../../components/column";
import { useLiveify } from "../../components/liveify";
import { removeUndefined } from "../../utils/filtering";
import { TableState, useInitialTableState, useStoreInitialState } from "../../utils/saveload";
import { IPlate } from "./model";

dayjs.extend(utc);

const namespace = "plateList-v1";

const allColumns: (keyof IPlate & string)[] = [
  "id",
  "project_id",
  "name",
  "file_path",
  "estimated_weight",
  "estimated_time",
  "comment",
  "registered",
];

/** Format seconds as HH:mm:ss */
function formatDuration(seconds: number | undefined | null): string {
  if (seconds === undefined || seconds === null) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

export const PlateList = () => {
  const t = useTranslate();
  const invalidate = useInvalidate();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const projectIdFromUrl = searchParams.get("project_id") ? Number(searchParams.get("project_id")) : undefined;

  // Load initial state
  const initialState = useInitialTableState(namespace);

  // Fetch data from the API
  const { tableProps, sorters, setSorters, filters, setFilters, currentPage, pageSize, setCurrentPage } =
    useTable<IPlate>({
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
        initial: projectIdFromUrl
          ? [{ field: "project_id", operator: "eq", value: projectIdFromUrl }]
          : initialState.filters,
      },
      liveMode: "manual",
      onLiveEvent(event) {
        if (event.type === "created" || event.type === "deleted") {
          invalidate({
            resource: "plate",
            invalidates: ["list"],
          });
        }
      },
    });

  // Create state for the columns to show
  const [showColumns, setShowColumns] = useState<string[]>(initialState.showColumns ?? allColumns);

  // Store state in local storage
  const tableState: TableState = {
    sorters,
    filters,
    pagination: { currentPage, pageSize },
    showColumns,
  };
  useStoreInitialState(namespace, tableState);

  // Collapse the dataSource to a mutable list
  const queryDataSource: IPlate[] = useMemo(() => {
    return (tableProps.dataSource || []).map((record) => ({ ...record }));
  }, [tableProps.dataSource]);
  const dataSource = useLiveify(
    "plate",
    queryDataSource,
    useCallback((record: IPlate) => record, []),
  );

  if (tableProps.pagination) {
    tableProps.pagination.showSizeChanger = true;
  }

  const { editUrl, cloneUrl, createUrl } = useNavigation();
  const actions = (record: IPlate) => [
    { name: "Edit", icon: <EditOutlined />, link: editUrl("plate", record.id) },
    { name: "Clone", icon: <PlusSquareOutlined />, link: cloneUrl("plate", record.id) },
    { name: "Add Print Job", icon: <PrinterOutlined />, link: `${createUrl("print_job")}?plate_id=${record.id}` },
  ];

  const commonProps = {
    t,
    navigate,
    actions,
    dataSource,
    tableState,
    sorter: true,
  };

  return (
    <List
      headerButtons={({ defaultButtons }) => (
        <>
          <Button
            type="primary"
            icon={<FilterOutlined />}
            onClick={() => {
              setFilters([], "replace");
              setSorters([{ field: "id", order: "asc" }]);
              setCurrentPage(1);
            }}
          >
            Clear Filters
          </Button>
          <Button
            type="primary"
            icon={<EditOutlined />}
            onClick={() => setShowColumns(showColumns.length === allColumns.length ? ["id"] : allColumns)}
          >
            Toggle Columns
          </Button>
          {defaultButtons}
        </>
      )}
    >
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
            title: "ID",
            width: 70,
          }),
          SortedColumn({
            ...commonProps,
            id: "project_id",
            title: "Project ID",
            width: 100,
          }),
          SortedColumn({
            ...commonProps,
            id: "name",
            title: "Name",
          }),
          SortedColumn({
            ...commonProps,
            id: "file_path",
            title: "File Path",
          }),
          NumberColumn({
            ...commonProps,
            id: "estimated_weight",
            title: "Est. Weight",
            unit: "g",
            maxDecimals: 1,
            width: 130,
          }),
          {
            dataIndex: "estimated_time",
            title: "Est. Time",
            hidden: !showColumns.includes("estimated_time"),
            width: 120,
            render: (value: number | undefined) => formatDuration(value),
          },
          SortedColumn({
            ...commonProps,
            id: "comment",
            title: "Comment",
          }),
          DateColumn({
            ...commonProps,
            id: "registered",
            title: "Registered",
            width: 200,
          }),
          ActionsColumn<IPlate>("Actions", actions),
        ])}
      />
    </List>
  );
};

export default PlateList;
