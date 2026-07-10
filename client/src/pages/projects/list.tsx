import { EditOutlined, FileAddOutlined, FilterOutlined, PrinterOutlined, PlusSquareOutlined, UnorderedListOutlined } from "@ant-design/icons";
import { List, useTable } from "@refinedev/antd";
import { useInvalidate, useNavigation, useTranslate } from "@refinedev/core";
import { Button, Table } from "antd";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import {
  ActionsColumn,
  DateColumn,
  SortedColumn,
} from "../../components/column";
import { useLiveify } from "../../components/liveify";
import { removeUndefined } from "../../utils/filtering";
import { TableState, useInitialTableState, useStoreInitialState } from "../../utils/saveload";
import { IProject } from "./model";

dayjs.extend(utc);

const namespace = "projectList-v1";

const allColumns: (keyof IProject & string)[] = ["id", "name", "description", "link", "registered"];

export const ProjectList = () => {
  const t = useTranslate();
  const invalidate = useInvalidate();
  const navigate = useNavigate();

  // Load initial state
  const initialState = useInitialTableState(namespace);

  // Fetch data from the API
  const { tableProps, sorters, setSorters, filters, setFilters, currentPage, pageSize, setCurrentPage } =
    useTable<IProject>({
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
            resource: "project",
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
  const queryDataSource: IProject[] = useMemo(() => {
    return (tableProps.dataSource || []).map((record) => ({ ...record }));
  }, [tableProps.dataSource]);
  const dataSource = useLiveify(
    "project",
    queryDataSource,
    useCallback((record: IProject) => record, []),
  );

  if (tableProps.pagination) {
    tableProps.pagination.showSizeChanger = true;
  }

  const { editUrl, cloneUrl, createUrl, listUrl } = useNavigation();
  const actions = (record: IProject) => [
    { name: "Edit", icon: <EditOutlined />, link: editUrl("project", record.id) },
    { name: "Clone", icon: <PlusSquareOutlined />, link: cloneUrl("project", record.id) },
    { name: "Add Plate", icon: <FileAddOutlined />, link: `${createUrl("plate")}?project_id=${record.id}` },
    { name: "List Plates", icon: <UnorderedListOutlined />, link: `${listUrl("plate")}?project_id=${record.id}` },
    { name: "List Print Jobs", icon: <PrinterOutlined />, link: `${listUrl("print_job")}?project_id=${record.id}` },
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
            id: "name",
            title: "Name",
          }),
          SortedColumn({
            ...commonProps,
            id: "description",
            title: "Description",
          }),
          {
            dataIndex: "link",
            title: "Link",
            hidden: !showColumns.includes("link"),
            render: (value: string | undefined) =>
              value ? (
                <a href={value} target="_blank" rel="noopener noreferrer">
                  {value}
                </a>
              ) : null,
          },
          DateColumn({
            ...commonProps,
            id: "registered",
            title: "Registered",
            width: 200,
          }),
          ActionsColumn<IProject>("Actions", actions),
        ])}
      />
    </List>
  );
};

export default ProjectList;
