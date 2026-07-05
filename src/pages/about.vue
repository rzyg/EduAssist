<script setup lang="ts">
import {h} from 'vue'
import {NCard, NList, NListItem, NSpace, NTag, useThemeVars, NAvatar} from 'naive-ui'

const themeVars = useThemeVars()

interface OpenSourceProject {
  name: string
  license: string
  copyright: string
}

const openSourceProjects: OpenSourceProject[] = [
  {
    name: 'Vue.js',
    license: 'MIT License',
    copyright: 'Copyright (c) 2013-present, Yuxi Evan You'
  },
  {
    name: 'Tauri',
    license: 'MIT License',
    copyright: 'Copyright (c) 2019-2024 Tauri Programme within The Commons Conservancy'
  },
  {
    name: 'Naive UI',
    license: 'MIT License',
    copyright: 'Copyright (c) 2021-present, TuSimple'
  },
  {
    name: 'Vite',
    license: 'MIT License',
    copyright: 'Copyright (c) 2019-present, Yuxi Evan You and Vite contributors'
  },
  {
    name: 'TypeScript',
    license: 'Apache License 2.0',
    copyright: 'Copyright (c) Microsoft Corporation'
  },
  {
    name: 'FastAPI',
    license: 'MIT License',
    copyright: 'Copyright (c) 2018 Sebastián Ramírez'
  },
  {
    name: 'Python',
    license: 'PSF License',
    copyright: 'Copyright (c) 2001-2024 Python Software Foundation'
  },
  {
    name: 'openpyxl',
    license: 'MIT License',
    copyright: 'Copyright (c) 2010 openpyxl'
  },
  {
    name: 'loguru',
    license: 'MIT License',
    copyright: 'Copyright (c) 2017 Delgan'
  }
]

function renderProject(project: OpenSourceProject) {
  return h(
      NListItem,
      {style: {padding: '16px 24px'}},
      () => h(NSpace, {vertical: true, size: 'small'}, {
        default: () => [
          h(NSpace, {align: 'center'}, {
            default: () => [
              h('span', {
                style: {
                  fontSize: '14px',
                  fontWeight: '500',
                  color: themeVars.value.textColor1
                }
              }, project.name),
              h(NTag, {size: 'small', type: 'info'}, {default: () => project.license})
            ]
          }),
          h('div', {
            style: {
              fontSize: '12px',
              color: themeVars.value.textColor3,
              lineHeight: '1.5'
            }
          }, project.copyright)
        ]
      })
  )
}


</script>

<template>
  <div class="info-container">
    <n-card title="关于" :bordered="false">
      <n-list>
        <n-list-item>
          <n-space vertical :size="12">
            <div class="section-title">开发者</div>
            <div class="section-content developer-section">
              <div class="developer-layout">
                <div class="developer-left">
                  <n-avatar
                      size="large"
                      round
                      src="src/assets/about/兰因.png"
                      fallback-src=""
                  />
                  <div class="developer-name">郭墨渊</div>
                  <div class="developer-nickname">(兰因)</div>
                </div>
                <div class="developer-right">
                  <div class="developer-desc">
                    我于2022年进入汝州一高就读，2026年毕业，现就读于河南牧业经济学院软件学院。饮水思源，在高中繁重的教务工作中，我深感老师们重复劳动的艰辛。于是，我利用所学专业知识，为母校定制开发了这款"下班工具箱"，希望能用代码为老师们减负，让教育回归纯粹。
                  </div>
                </div>
              </div>
            </div>

          </n-space>
        </n-list-item>

        <n-list-item>
          <n-space vertical :size="12">
            <div class="section-title">鸣谢</div>
            <div class="section-content">
              <p>
                本项目的顺利落地，离不开母校汝州一高各位领导与教职工的信任与支持。特别感谢在项目调研与测试阶段给予我宝贵建议的老师们，是你们的辛勤耕耘与包容，让这个工具得以贴合实际教学需求，真正实现“为教育减负”的初衷。</p>
              <p>
                同时，谨向以下开源项目及维护者致以最诚挚的敬意。本工具因开源而强大，本项目所引用的主要开源库包括但不限于：Vue.js、Tauri、Naive
                UI、Vite、TypeScript、FastAPI、Python、openpyxl、loguru。</p>
              <p>感谢每一位为社区无私奉献的开发者。</p>
            </div>
          </n-space>
        </n-list-item>

        <n-list-item>
          <n-space vertical :size="12">
            <div class="section-title">开源项目清单</div>
            <div class="section-content">
              <n-list bordered>
                <component
                    v-for="project in openSourceProjects"
                    :key="project.name"
                    :is="renderProject(project)"
                />
              </n-list>
            </div>
          </n-space>
        </n-list-item>

        <n-list-item>
          <n-space vertical :size="12">
            <div class="section-title">📄 软件许可协议 <span class="license-type">MIT License</span></div>
            <div class="section-content license-section">
              <div class="license-notice">
                ⚠️ 本软件是为汝州一高教师提供的非官方工具，并非由汝州一高官方发布或支持。
              </div>
              <div class="license-text">
                Copyright (c) 2026 兰因<br/><br/>
                Permission is hereby granted, free of charge, to any person obtaining a copy
                of this software and associated documentation files (the "Software"), to deal
                in the Software without restriction, including without limitation the rights
                to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
                copies of the Software, and to permit persons to whom the Software is
                furnished to do so, subject to the following conditions:<br/><br/>
                The above copyright notice and this permission notice shall be included in all
                copies or substantial portions of the Software.<br/><br/>
                THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
                IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
                FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
                AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
                LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
                OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
                SOFTWARE.
              </div>
            </div>
          </n-space>
        </n-list-item>
      </n-list>
    </n-card>
  </div>
</template>

<style scoped>.info-container {
  height: 100vh;
  overflow: auto;
  margin: 0;
  padding: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.section-content {
  font-size: 14px;
  color: #666;
  line-height: 1.6;
}

.developer-section {
  padding: 8px 0;
}

.developer-layout {
  display: flex;
  gap: 32px;
  align-items: flex-start;
}

.developer-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
}

.developer-name, .developer-nickname {
  height: 1.2rem;
  font-size: 0.9rem;
  font-weight: 500;
  color: #333;
  text-align: center;
  margin: 0;
  padding: 0;
}

.developer-nickname {
  font-style: italic;
  font-size: 0.8rem;
}

.developer-right {
  flex: 1;
  min-width: 0;
}

.developer-desc {
  font-size: 14px;
  color: #666;
  line-height: 1.8;
  text-align: justify;
}

.license-section {
  padding: 8px 0;
}

.license-type {
  display: inline-block;
  font-size: 14px;
  font-weight: 600;
  color: #18a058;
  padding: 4px 12px;
  background-color: #f0f9f4;
  border-radius: 4px;
}

.license-notice {
  font-size: 13px;
  color: #ff6b6b;
  background-color: #fff5f5;
  padding: 10px 12px;
  border-radius: 6px;
  border-left: 3px solid #ff6b6b;
  margin-bottom: 16px;
  line-height: 1.6;
}

.license-text {
  font-size: 12px;
  color: #999;
  line-height: 1.8;
  font-family: 'Courier New', monospace;
  background-color: #fafafa;
  padding: 12px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>