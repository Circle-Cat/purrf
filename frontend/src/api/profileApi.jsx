import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

export async function getMyProfile({ fields } = {}) {
  let url = API_ENDPOINTS.MY_PROFILE;
  if (Array.isArray(fields) && fields.length > 0) {
    const params = new URLSearchParams();
    params.set("fields", fields.join(","));
    url += `?${params.toString()}`;
  }
  return await request.get(url);
}

export async function updateMyProfile(profile) {
  const url = API_ENDPOINTS.MY_PROFILE;
  return await request.patch(url, profile);
}
