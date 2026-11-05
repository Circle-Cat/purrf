import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

export async function getUserPermissions() {
  return await request.get(API_ENDPOINTS.MY_PERMISSIONS);
}
