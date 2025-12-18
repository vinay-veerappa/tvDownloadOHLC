import { redirect } from 'next/navigation'

export default function LiveChartPage() {
    redirect('/chart?mode=live')
}
