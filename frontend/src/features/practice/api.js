export function practiceApi(request, studentPath) {
  return {
    bank: (id, path, method = 'GET', body) => request(`${studentPath(id)}/${path}`, { method, body }),
  }
}
