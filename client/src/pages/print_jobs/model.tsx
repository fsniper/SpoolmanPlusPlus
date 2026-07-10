export interface IPrintJobSpool {
  spool_id: number;
  weight_used: number;
}

export interface IPrintJob {
  id: number;
  registered: string;
  plate_id: number;
  status: string;
  start_time?: string;
  end_time?: string;
  printer_id?: number;
  comment?: string;
  spool_usages: IPrintJobSpool[];
}
