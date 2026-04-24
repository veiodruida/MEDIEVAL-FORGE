import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Theme } from '@radix-ui/themes'
import * as Toast from '@radix-ui/react-toast'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 1000 * 30 },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Toast.Provider swipeDirection="right">
      <Theme appearance="light" accentColor="iris" radius="medium">
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </Theme>
      <Toast.Viewport className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 outline-none" />
    </Toast.Provider>
  </React.StrictMode>,
)
