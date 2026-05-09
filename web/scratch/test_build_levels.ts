import { buildLevels } from '../lib/options-live-v3/adapters'
import 'dotenv/config'

async function main() {
  console.log('Building levels for SPY...')
  const result = await buildLevels('SPY')
  console.log(JSON.stringify(result, null, 2))
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
