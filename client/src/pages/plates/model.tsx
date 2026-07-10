export interface IPlate {
  id: number;
  registered: string;
  project_id: number;
  name: string;
  file_path?: string;
  estimated_weight?: number;
  estimated_time?: number;
  comment?: string;
}
