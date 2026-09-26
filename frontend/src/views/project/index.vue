<template>
  <section class="page" data-module="project">
    <header class="page-head">
      <div>
        <h2>检测项目管理</h2>
        <p class="page-desc">维护检测项目，围绕项目编码、项目名称、检测方法、方法标准号做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检测项目</button>
        <button class="btn" type="button" @click="exportRows">导出检测项目清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyQuery">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="`按${field.label}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">
            <button
              v-if="column === SORT_FIELD"
              class="link sort-btn"
              type="button"
              :title="`按${SORT_FIELD}排序`"
              @click="toggleSort"
            >
              {{ column }} {{ sortOrder === 'asc' ? '↑' : sortOrder === 'desc' ? '↓' : '⇅' }}
            </button>
            <template v-else>{{ column }}</template>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length && !errorMessage">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
        <tr v-if="!rows.length && errorMessage">
          <td :colspan="columns.length + 1" class="empty-state error-text">{{ errorMessage }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检测项目记录</span>
      <span v-if="errorMessage && rows.length" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/project'
const columns = ["项目编码", "项目名称", "检测方法", "方法标准号", "检出限", "计量单位", "收费单价", "项目状态"]
const actions = ["启用项目", "提交修订", "停用项目"]
const statuses = ["草稿", "已启用", "待修订", "已停用"]
const stats = [{"label": "启用项目", "value": 0}, {"label": "待修订项目", "value": 0}, {"label": "本月新增项目", "value": 0}]

// 组合检索条件：key 是接口参数名，label 是页面展示名；多个条件按“且”叠加
const filterFields = [
  { key: 'code', label: '项目编码' },
  { key: 'standard', label: '方法标准号' },
  { key: 'unit', label: '计量单位' },
] as const
const SORT_FIELD = '收费单价'

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = reactive<Record<string, string>>({ code: '', standard: '', unit: '' })
const sortOrder = ref('') // '' 不排序，'asc' 升序，'desc' 降序

const hasConditions = computed(
  () => sortOrder.value !== '' || filterFields.some((field) => filters[field.key].trim() !== ''),
)
const emptyText = computed(() =>
  hasConditions.value
    ? '当前组合条件下没有匹配的检测项目，可调整或重置条件后再试'
    : '暂无检测项目数据，可先登记检测项目',
)

function firstValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value) && value.length) return String(value[0] ?? '')
  return ''
}

// 地址栏是条件的唯一落点：刷新、前进后退都能原样恢复
function syncFromQuery() {
  for (const field of filterFields) {
    filters[field.key] = firstValue(route.query[field.key])
  }
  const sort = firstValue(route.query.sort)
  const order = firstValue(route.query.order)
  sortOrder.value = sort === SORT_FIELD ? (order === 'desc' ? 'desc' : 'asc') : ''
}

function applyQuery() {
  const query: Record<string, string> = {}
  for (const field of filterFields) {
    const value = filters[field.key].trim()
    if (value) query[field.key] = value
  }
  if (sortOrder.value) {
    query.sort = SORT_FIELD
    query.order = sortOrder.value
  }
  void router.replace({ query })
}

function toggleSort() {
  sortOrder.value = sortOrder.value === '' ? 'asc' : sortOrder.value === 'asc' ? 'desc' : ''
  applyQuery()
}

function resetFilters() {
  for (const field of filterFields) {
    filters[field.key] = ''
  }
  sortOrder.value = ''
  applyQuery()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '检测项目登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('检测项目动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测项目操作失败'
  }
}

async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json()
    const detail = payload?.detail
    if (typeof detail === 'string' && detail) return detail
    if (Array.isArray(detail) && detail.length) {
      return detail.map((item: { msg?: string }) => item?.msg ?? '').filter(Boolean).join('；') || fallback
    }
  } catch {
    // 响应体不是 JSON 时走兜底文案
  }
  return fallback
}

async function reload() {
  errorMessage.value = ''
  // 查询参数直接取自地址栏并原样透传：条件互相冲突时由后端给出说明，这里不擅自取舍
  const query = new URLSearchParams()
  for (const field of filterFields) {
    const raw = route.query[field.key]
    for (const value of Array.isArray(raw) ? raw : [raw]) {
      if (typeof value === 'string' && value.trim()) query.append(field.key, value.trim())
    }
  }
  const sort = firstValue(route.query.sort)
  if (sort) {
    query.set('sort', sort)
    query.set('order', firstValue(route.query.order) || 'asc')
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error(await errorDetail(response, '检测项目列表读取失败'))
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    // 条件有问题时清空结果并说明原因，绝不把全量数据摊出来
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof Error ? error.message : '检测项目列表读取失败'
  }
}

// 输入停 300ms 后自动生效，调整条件结果立刻跟着变；排序与重置走 applyQuery 立即生效
let debounceTimer: number | undefined
watch(
  filters,
  () => {
    window.clearTimeout(debounceTimer)
    debounceTimer = window.setTimeout(applyQuery, 300)
  },
)

watch(
  () => route.query,
  () => {
    syncFromQuery()
    void reload()
  },
  { immediate: true },
)
</script>

<style scoped>
.sort-btn {
  font-size: 13px;
}
</style>
