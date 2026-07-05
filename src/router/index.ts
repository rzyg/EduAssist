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
        }
    ]
})

export default router
