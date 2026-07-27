import {createRouter, createWebHistory} from 'vue-router'
import Homepage from '../pages/homepage.vue'

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            name: 'home',
            component: Homepage
        },
        {
            path: '/transcript',
            name: 'transcript',
            component: () => import('../pages/score/transcript.vue')
        },
        {
            path: '/analysis',
            name: 'analysis',
            component: () => import('../pages/score/analysis.vue')
        }, {
            path: '/about',
            name: 'about',
            component: () => import('../pages/about.vue')
        }, {
            path: '/setting',
            name: 'setting',
            component: () => import('../pages/setting.vue')
        }, {
            path: '/fuck-the-online-class',
            name: 'fuck-the-online-class',
            component: () => import('../pages/construction.vue')
        }, {
            path: '/merge',
            name: 'merge',
            component: () => import('../pages/pdf/merge.vue')
        }, {
            path: '/split',
            name: 'split',
            component: () => import('../pages/construction.vue')
        }, {
            path: '/allowance',
            name: 'allowance',
            component: () => import('../pages/construction.vue')
        }
    ]
})

export default router
