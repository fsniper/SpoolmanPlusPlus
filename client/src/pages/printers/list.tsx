import { EditOutlined, FilterOutlined, PlusSquareOutlined } from "@ant-design/icons";
import { List, useTable } from "@refinedev/antd";
import { useInvalidate, useNavigation, useTranslate } from "@refinedev/core";
import { Button, Table } from "antd";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { ActionsColumn, DateColumn, SortedColumn } from "../../components/column";
import { useLiveify } from "../../components/liveify";
import { removeUndefined } from "../../utils/filtering";
import { TableState, useInitialTableState, useStoreInitialState } from "../../utils/saveload";
import { IPrinter } from "./model";

dayjs.extend(utc);

const namespace = "printerList-v1";
const allColumns: (keyof IPrinter & string)[] = ["id", "name", "model", "location", "comment", "registered"];

export const PrinterList = () => {
  const t = useTranslate();
  const invalidate = useInvalidate();
  const navigate = useNavigate();
  const initialState = useInitialTableState(namespace);

  const { tableProps, sorters, setSorters, filters, setFilters, currentPage, pageSize, setCurrentPage } =
    useTable<IPrinter>({
      syncWithLocation: false,
      pagination: { mode: "server", currentPage: initialState.pagination.currentPage, pageSize: initialState.pagination.pageSize },
      sorters: { mode: "server", initial: initialState.sorters },
      filters: { mode: "server", initial: initialState.filters },
      liveMode: "manual",
      onLiveEvent(event) {
        if (event.type === "created" || event.type === "deleted") {
          invalidate({ resource: "printer", invalidates: ["list"] });
        }
      },
    });

  const [showColumns, setShowColumns] = useState<string[]>(initialState.showColumns ?? allColumns);

  const tableState: TableState = { sorters, filters, pagination: { currentPage, pageSize }, showColumns };
  useStoreInitialState(namespace, tableState);

  const queryDataSource: IPrinter[] = useMemo(() => (tableProps.dataSource || []).map((r) => ({ ...r })), [tableProps.dataSource]);
  const dataSource = useLiveify("printer", queryDataSource, useCallback((r: IPrinter) => r, []));

  if (tableProps.pagination) tableProps.pagination.showSizeChanger = true;

  const { editUrl, cloneUrl } = useNavigation();
  const actions = (record: IPrinter) => [
    { name: "Edit", icon: <EditOutlined />, link: editUrl("printer", record.id) },
    { name: "Clone", icon: <PlusSquareOutlined />, link: cloneUrl("printer", record.id) },
  ];

  const commonProps = { t, navigate, actions, dataSource, tableState, sorter: true };

  return (
    <List
      headerButtons={({ defaultButtons }) => (
        <>
          <Button type="primary" icon={<FilterOutlined />} onClick={() => { setFilters([], "replace"); setSorters([{ field: "id", order: "asc" }]); setCurrentPage(1); }}>
            Clear Filters
          </Button>
          <Button type="primary" icon={<EditOutlined />} onClick={() => setShowColumns(showColumns.length === allColumns.length ? ["id"] : allColumns)}>
            Toggle Columns
          </Button>
          {defaultButtons}
        </>
      )}
    >
      <Table {...tableProps} sticky tableLayout="auto" scroll={{ x: "max-content" }} dataSource={dataSource} rowKey="id"
        columns={removeUndefined([
          SortedColumn({ ...commonProps, id: "id", title: "ID", width: 70 }),
          SortedColumn({ ...commonProps, id: "name", title: "Name" }),
          SortedColumn({ ...commonProps, id: "model", title: "Model" }),
          SortedColumn({ ...commonProps, id: "location", title: "Location" }),
          SortedColumn({ ...commonProps, id: "comment", title: "Comment" }),
          DateColumn({ ...commonProps, id: "registered", title: "Registered", width: 200 }),
          ActionsColumn<IPrinter>("Actions", actions),
        ])}
      />
    </List>
  );
};

export default PrinterList;
