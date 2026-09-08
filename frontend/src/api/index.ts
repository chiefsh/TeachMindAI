import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

/** 拦截器已解包 res.data，调用方拿到的是 T 而不是 AxiosResponse<T>。 */
export interface ApiClient {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
}

const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

instance.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

instance.interceptors.response.use(
  (res) => res.data,
  async (err) => {
    const status = err.response?.status
    let payload = err.response?.data
    if (payload instanceof Blob) {
      try {
        const text = await payload.text()
        payload = JSON.parse(text)
      } catch {
        payload = null
      }
    }
    const rawDetail = payload?.detail
    const msg = Array.isArray(rawDetail)
      ? rawDetail.map((d: any) => d?.msg).filter(Boolean).join('；') || '请求参数有误'
      : (rawDetail || err.message || '请求失败')
    if (status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
      ElMessage.error('登录已过期，请重新登录')
    } else if (status === 413) {
      ElMessage.error('文件过大，最大支持 500MB')
    } else {
      ElMessage.error(typeof msg === 'string' ? msg : '请求失败')
    }
    return Promise.reject(err)
  },
)

const request = instance as unknown as ApiClient
export default request
