import request from "@/utils/request";

export async function getMyProfile({ fields } = {}) {
  let url = "/profiles/me";
  if (Array.isArray(fields) && fields.length > 0) {
    const params = new URLSearchParams();
    params.set("fields", fields.join(","));
    url += `?${params.toString()}`;
  }
  return await request.get(url);
}
