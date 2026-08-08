<script lang="ts" setup>
import {computed, onMounted, ref} from 'vue'
import {useMessage} from 'naive-ui'
import {apiGet, apiPut} from '../../config'

/** 接口返回的单日记录 */
interface HolidayRecord {
    holiday: boolean
    leave_school: boolean
    return_school: boolean
    schedule_modification: string | null
    remark: string | null
    date?: string
}

/** 课表修改结构：上午（早读+1-4 节）、下午（1-4 节）、晚上（1-2 节） */
interface ScheduleForm {
    morning: Record<string, boolean>
    afternoon: Record<string, boolean>
    evening: Record<string, boolean>
}

const message = useMessage()

// ── 当前选择的年、月 ──
const today = new Date()
const currentYear = ref<number>(today.getFullYear())
const currentMonth = ref<number>(today.getMonth() + 1)

// 年份选择范围
const yearOptions = Array.from({length: 21}, (_, i) => currentYear.value - 10 + i)

const monthOptions = [
    {label: '一月', value: 1}, {label: '二月', value: 2}, {label: '三月', value: 3},
    {label: '四月', value: 4}, {label: '五月', value: 5}, {label: '六月', value: 6},
    {label: '七月', value: 7}, {label: '八月', value: 8}, {label: '九月', value: 9},
    {label: '十月', value: 10}, {label: '十一月', value: 11}, {label: '十二月', value: 12},
]

// ── 按年缓存的节假日数据 ──
const holidayByYear = ref<Record<number, Record<string, HolidayRecord>>>({})

// 课表各时段配置（全部中文）
const scheduleSections: { part: keyof ScheduleForm; label: string; periods: [string, string][] }[] = [
    {part: 'morning', label: '上午', periods: [['early_read', '早读'], ['1', '第一节'], ['2', '第二节'], ['3', '第三节'], ['4', '第四节']]},
    {part: 'afternoon', label: '下午', periods: [['1', '第一节'], ['2', '第二节'], ['3', '第三节'], ['4', '第四节']]},
    {part: 'evening', label: '晚上', periods: [['1', '第一节'], ['2', '第二节']]},
]

// 课表修改默认全部勾选
const DEFAULT_SCHEDULE: ScheduleForm = {
    morning: {early_read: true, '1': true, '2': true, '3': true, '4': true},
    afternoon: {'1': true, '2': true, '3': true, '4': true},
    evening: {'1': true, '2': true},
}

function cloneSchedule(): ScheduleForm {
    return JSON.parse(JSON.stringify(DEFAULT_SCHEDULE)) as ScheduleForm
}

// ── 数据加载 ──
async function loadYear(year: number) {
    if (holidayByYear.value[year]) return
    try {
        const data = await apiGet<{holiday: Record<string, HolidayRecord>}>(
            `/api/v1/allowance/get_calendar?year=${year}`
        )
        holidayByYear.value[year] = data.holiday || {}
    } catch (e: any) {
        message.error(`加载节假日数据失败：${e.message || e}`)
        holidayByYear.value[year] = {}
    }
}

function onYearChange() {
    void loadYear(currentYear.value)
}

function onMonthChange() {
    void loadYear(currentYear.value)
}

// ── 日历网格（仅当月日期，按实际星期对齐，周一开头）──
const weekHeaders = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const calendarCells = computed<(Date | null)[]>(() => {
    const year = currentYear.value
    const month = currentMonth.value
    const first = new Date(year, month - 1, 1)
    // 当月 1 日是周几（周一为一周开头：周日(0) → 6，周一(1) → 0）
    const startWeekday = (first.getDay() + 6) % 7
    const daysInMonth = new Date(year, month, 0).getDate()

    const cells: (Date | null)[] = []
    // 1 日前的空位（不显示其他月份日期，仅占位对齐星期）
    for (let i = 0; i < startWeekday; i++) {
        cells.push(null)
    }
    for (let d = 1; d <= daysInMonth; d++) {
        cells.push(new Date(year, month - 1, d))
    }
    // 末尾补齐到整行（空占位，不显示其他月份日期）
    while (cells.length % 7 !== 0) {
        cells.push(null)
    }
    return cells
})

// 每周（最多 7 格）分组，便于表格按行渲染
const calendarRows = computed<(Date | null)[][]>(() => {
    const rows: (Date | null)[][] = []
    for (let i = 0; i < calendarCells.value.length; i += 7) {
        rows.push(calendarCells.value.slice(i, i + 7))
    }
    return rows
})

function dayKey(date: Date): string {
    return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function dayRecord(date: Date): HolidayRecord | undefined {
    return holidayByYear.value[date.getFullYear()]?.[dayKey(date)]
}

/** 课表修改数据中是否存在停课/调整（任一节次为 false） */
function scheduleHasChanges(raw: string | null): boolean {
    if (!raw) return false
    try {
        const obj = JSON.parse(raw) as Partial<ScheduleForm>
        for (const section of scheduleSections) {
            const part = obj[section.part]
            if (!part || typeof part !== 'object') continue
            for (const [key] of section.periods) {
                if (part[key] === false) return true
            }
        }
        return false
    } catch {
        return true
    }
}

/** 是否有课表修改或备注数据（课表全为正常上课时不视为修改） */
function hasEditData(date: Date): boolean {
    const rec = dayRecord(date)
    if (!rec) return false
    if (rec.remark) return true
    return scheduleHasChanges(rec.schedule_modification)
}

/** 底色优先级：离校 > 返校 > 假期（淡蓝）> 课表修改/备注（浅粉） */
function dayClass(date: Date): string {
    const rec = dayRecord(date)
    if (!rec) return ''
    if (rec.leave_school) return 'mark-leave'
    if (rec.return_school) return 'mark-return'
    if (rec.holiday) return 'mark-holiday'
    if (hasEditData(date)) return 'mark-edit'
    return ''
}

// ── 编辑弹窗 ──
const showEditor = ref(false)
const editingDay = ref<Date | null>(null)
const editForm = ref({
    leaveSchool: false,
    returnSchool: false,
    schedule: cloneSchedule(),
    remark: '',
})
// 打开弹窗时的原始状态快照（用于判断是否发生修改）
const editOrigin = ref<{leaveSchool: boolean; returnSchool: boolean; schedule: ScheduleForm} | null>(null)

const holidayType = computed({
    get: () => (editForm.value.leaveSchool ? 'leave' : editForm.value.returnSchool ? 'return' : 'none'),
    set: (v: string) => {
        editForm.value.leaveSchool = v === 'leave'
        editForm.value.returnSchool = v === 'return'
    },
})

function parseSchedule(raw: string | null): ScheduleForm {
    if (!raw) return cloneSchedule()
    try {
        const obj = JSON.parse(raw) as Partial<ScheduleForm>
        const merged = cloneSchedule()
        for (const section of scheduleSections) {
            const part = obj[section.part]
            if (part && typeof part === 'object') {
                merged[section.part] = {...merged[section.part], ...part}
            }
        }
        return merged
    } catch {
        return cloneSchedule()
    }
}

function openEditor(date: Date) {
    const rec = dayRecord(date)
    editingDay.value = date
    const schedule = parseSchedule(rec?.schedule_modification ?? null)
    const leaveSchool = rec?.leave_school ?? false
    const returnSchool = rec?.return_school ?? false
    editForm.value = {
        leaveSchool,
        returnSchool,
        schedule,
        remark: rec?.remark ?? '',
    }
    // 保存原始状态快照（深拷贝），用于判断是否发生修改
    editOrigin.value = {
        leaveSchool,
        returnSchool,
        schedule: JSON.parse(JSON.stringify(schedule)) as ScheduleForm,
    }
    showEditor.value = true
}

async function saveEditor() {
    if (!editingDay.value) return

    // 修改课表（存在停课）、或修改了离校/返校时必须填写备注；
    // 课表全为正常上课且未修改离校/返校时无需备注
    const origin = editOrigin.value
    if (origin) {
        const scheduleHasStops = scheduleHasChanges(JSON.stringify(editForm.value.schedule))
        const dayTypeChanged =
            editForm.value.leaveSchool !== origin.leaveSchool
            || editForm.value.returnSchool !== origin.returnSchool
        if ((scheduleHasStops || dayTypeChanged) && !editForm.value.remark.trim()) {
            message.warning('修改课表、离校或返校时必须填写备注')
            return
        }
    }

    const year = editingDay.value.getFullYear()
    const payload = {
        year,
        month_day: dayKey(editingDay.value),
        leave_school: editForm.value.leaveSchool,
        return_school: editForm.value.returnSchool,
        schedule_modification: editForm.value.schedule,
        remark: editForm.value.remark,
    }
    try {
        await apiPut('/api/v1/allowance/update_holiday', payload)
        message.success('保存成功')
        showEditor.value = false
        delete holidayByYear.value[year]
        await loadYear(year)
    } catch (e: any) {
        message.error(`保存失败：${e.message || e}`)
    }
}

onMounted(async () => {
    await loadYear(currentYear.value)
})
</script>

<template>
  <div class="calendar-container">
    <n-card title="校历" style="height: 100vh; padding-top: 1rem">
      <!-- 年月选择 -->
      <n-space align="center" style="margin-bottom: 12px">
        <n-select
            v-model:value="currentYear"
            :options="yearOptions.map(y => ({label: `${y} 年`, value: y}))"
            style="width: 110px"
            @update:value="onYearChange"
        />
        <n-select
            v-model:value="currentMonth"
            :options="monthOptions"
            style="width: 110px"
            @update:value="onMonthChange"
        />
        <n-text depth="3">点击日期可编辑离校、返校日、课表修改与备注</n-text>
      </n-space>

      <!-- 图例 -->
      <n-space style="margin-bottom: 8px" :size="16">
        <span class="legend"><span class="legend-dot leave"></span>离校日</span>
        <span class="legend"><span class="legend-dot ret"></span>返校日</span>
        <span class="legend"><span class="legend-dot holiday"></span>假期</span>
        <span class="legend"><span class="legend-dot edit"></span>课表修改/备注</span>
      </n-space>

      <!-- 日历网格（仅当月） -->
      <div class="calendar-grid">
        <div class="calendar-row calendar-header">
          <div v-for="week in weekHeaders" :key="week" class="calendar-cell week-header">
            {{ week }}
          </div>
        </div>
        <div v-for="(row, rowIndex) in calendarRows" :key="rowIndex" class="calendar-row">
          <div
              v-for="(cell, cellIndex) in row"
              :key="cellIndex"
              class="calendar-cell day-cell"
              :class="[cell ? dayClass(cell) : 'empty']"
              @click="cell && openEditor(cell)"
          >
            <template v-if="cell">
              <div class="day-number">{{ cell.getDate() }}</div>
              <div class="day-tags">
                <div v-if="dayRecord(cell)?.leave_school" class="day-tag leave">离校</div>
                <div v-else-if="dayRecord(cell)?.return_school" class="day-tag ret">返校</div>
                <div v-if="hasEditData(cell)" class="day-tag edit">修改</div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 编辑弹窗 -->
      <n-modal
          v-model:show="showEditor"
          preset="card"
          style="width: 560px"
          title="编辑日期设置"
          :bordered="false"
      >
        <n-form label-placement="left" label-width="90">
          <n-form-item label="日期">
            <n-text>
              {{ editingDay ? `${editingDay.getFullYear()} 年 ${editingDay.getMonth() + 1} 月 ${editingDay.getDate()} 日` : '' }}
            </n-text>
          </n-form-item>

          <n-form-item label="离校、返校">
            <n-radio-group v-model:value="holidayType">
              <n-radio value="none">无</n-radio>
              <n-radio value="leave">离校日</n-radio>
              <n-radio value="return">返校日</n-radio>
            </n-radio-group>
          </n-form-item>

          <n-form-item label="课表修改">
            <div class="schedule-editor">
              <div v-for="section in scheduleSections" :key="section.part" class="schedule-block">
                <n-text strong>{{ section.label }}</n-text>
                <n-space :size="[8, 4]" wrap>
                  <n-checkbox
                      v-for="[key, label] in section.periods"
                      :key="key"
                      :checked="editForm.schedule[section.part][key]"
                      @update:checked="(v: boolean) => { editForm.schedule[section.part][key] = v }"
                  >
                    {{ label }}
                  </n-checkbox>
                </n-space>
              </div>
              <n-text depth="3" style="font-size: 12px;">勾选表示该节次正常上课，取消勾选表示停课或调整</n-text>
            </div>
          </n-form-item>

          <n-form-item label="备注">
            <n-input
                v-model:value="editForm.remark"
                type="textarea"
                placeholder="修改课表、离校或返校时必须填写备注"
                :autosize="{minRows: 2, maxRows: 4}"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showEditor = false">取消</n-button>
            <n-button type="primary" @click="saveEditor">保存</n-button>
          </n-space>
        </template>
      </n-modal>
    </n-card>
  </div>
</template>

<style scoped>
.calendar-container {
  margin: 0;
  padding: 0;
}

.legend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}

.legend-dot.leave {
  background-color: #ffb74d;
}

.legend-dot.ret {
  background-color: #66bb6a;
}

.legend-dot.holiday {
  background-color: #90caf9;
}

.legend-dot.edit {
  background-color: #f8bbd0;
}

/* ── 日历网格 ── */
.calendar-grid {
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}

.calendar-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}

.calendar-row + .calendar-row {
  border-top: 1px solid #f0f0f0;
}

.calendar-cell {
  min-height: 72px;
  padding: 4px;
  box-sizing: border-box;
}

.calendar-cell + .calendar-cell {
  border-left: 1px solid #f0f0f0;
}

.week-header {
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #666;
  background: #fafafa;
  font-weight: 500;
}

.day-cell {
  cursor: pointer;
  transition: background-color 0.2s;
  border-radius: 0;
}

.day-cell:hover {
  background-color: rgba(50, 136, 237, 0.12);
}

.day-cell.mark-leave {
  background-color: #ffe0b2;
}

.day-cell.mark-return {
  background-color: #c8e6c9;
}

/* 假期（非返校、离校日）：淡蓝色标注 */
.day-cell.mark-holiday {
  background-color: #e3f2fd;
}

/* 课表修改/备注：浅粉色标注 */
.day-cell.mark-edit {
  background-color: #fce4ec;
}

.day-number {
  font-size: 15px;
  font-weight: 500;
}

.day-tags {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 2px;
}

.day-tag {
  font-size: 11px;
  line-height: 1.2;
  font-weight: 600;
  align-self: flex-start;
}

.day-tag.leave {
  color: #e65100;
}

.day-tag.ret {
  color: #2e7d32;
}

.day-tag.edit {
  color: #ad1457;
}

/* ── 课表编辑 ── */
.schedule-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.schedule-block {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
