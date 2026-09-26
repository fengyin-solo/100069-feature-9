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

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>项目编码</span>
        <input v-model="filters.code" placeholder="如 PROJ-0001" autocomplete="off" />
      </label>
      <label class="filter-item">
        <span>方法标准号</span>
        <input v-model="filters.standard" placeholder="如 GB/T 5750.4" autocomplete="off" />
      </label>
      <label class="filter-item">
        <span>计量单位</span>
        <input v-model="filters.unit" placeholder="如 mg/L" autocomplete="off" />
      </label>
      <label class="filter-item">
        <span>收费单价排序</span>
        <select v-model="sort">
          <option value="">默认排列</option>
          <option value="price_asc">单价从低到高</option>
          <option value="price_desc">单价从高到低</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
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
        <tr v-if="!loading && !rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            {{ emptyHint || '暂无检测项目数据，可先登记检测项目' }}
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检测项目记录</span>
      <span v-if="rows.length && emptyHint" class="hint-text">{{ emptyHint }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type SortValue = '' | 'price_asc' | 'price_desc'

const ENDPOINT = '/api/project'
const STORAGE_KEY = 'project-list-query'
const columns = ["项目编码", "项目名称", "检测方法", "方法标准号", "检出限", "计量单位", "收费单价", "项目状态"]
const actions = ["启用项目", "提交修订", "停用项目"]
const stats = [{"label": "启用项目", "value": 0}, {"label": "待修订项目", "value": 0}, {"label": "本月新增项目", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
const emptyHint = ref('')
const filters = ref<{ code: string; standard: string; unit: string }>(
  { code: '', standard: '', unit: '' },
)
const sort = ref<SortValue>('')

let requestSeq = 0
let debounceTimer: ReturnType<typeof setTimeout> | undefined

function persistQuery() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ filters: filters.value, sort: sort.value }))
  } catch {
    // 隐私模式等场景下存储不可用，不影响检索本身
  }
}

function restoreQuery() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as { filters?: Partial<typeof filters.value>; sort?: string }
    filters.value = {
      code: String(saved.filters?.code ?? ''),
      standard: String(saved.filters?.standard ?? ''),
      unit: String(saved.filters?.unit ?? ''),
    }
    sort.value = saved.sort === 'price_asc' || saved.sort === 'price_desc' ? saved.sort : ''
  } catch {
    // 旧版本或损坏的缓存直接忽略，按默认条件进入
  }
}

function resetFilters() {
  filters.value = { code: '', standard: '', unit: '' }
  sort.value = ''
  void reload()
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

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.value.code.trim()) params.set('code', filters.value.code.trim())
  if (filters.value.standard.trim()) params.set('standard', filters.value.standard.trim())
  if (filters.value.unit.trim()) params.set('unit', filters.value.unit.trim())
  if (sort.value) params.set('sort', sort.value)

  const seq = ++requestSeq
  loading.value = true
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      let detail = '检测项目列表读取失败'
      try {
        const body = await response.json()
        if (typeof body.detail === 'string') detail = body.detail
      } catch {
        // 响应体不是 JSON 时沿用默认说明
      }
      throw new Error(detail)
    }
    const payload = await response.json()
    // 输入很快变化时，只采纳最后一次请求的结果，避免旧结果覆盖新结果
    if (seq !== requestSeq) return
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    emptyHint.value = typeof payload.hint === 'string' ? payload.hint : ''
  } catch (error) {
    if (seq !== requestSeq) return
    errorMessage.value = error instanceof Error ? error.message : '检测项目列表读取失败'
    rows.value = []
    total.value = 0
    emptyHint.value = ''
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

// 先恢复上次的检索条件与排序，再注册监听，避免恢复动作本身触发一次多余请求
restoreQuery()

// 检索条件变化：去抖后立刻刷新；排列次序切换：马上刷新
watch(filters, () => {
  persistQuery()
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => void reload(), 300)
}, { deep: true })
watch(sort, () => {
  persistQuery()
  void reload()
})

onMounted(() => {
  void reload()
})
</script>
