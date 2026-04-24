import { useState } from 'react'
import { Dialog, Button, Flex, Text, RadioGroup } from '@radix-ui/themes'
import { useSaveStrategy, setStrategy } from '../../services/persistence'
import type { SaveStrategy } from '../../types/editing'

/**
 * SettingsPanel (D-07) — Radix Dialog with RadioGroup for save strategy selection.
 *
 * UI-SPEC note: Sheet is NOT in @radix-ui/themes; Dialog is the correct primitive.
 * Strategy persisted to localStorage key 'mf:save-strategy' via persistence service.
 *
 * Copywriting per UI-SPEC §Copywriting Contract:
 *   title:   "Configurações de Salvamento"
 *   options: "Automático (1.5s após edição)" / "Por operação" / "Manual (Ctrl+S)"
 */
export function SettingsPanel() {
  const strategy = useSaveStrategy()
  const [open, setOpen] = useState(false)

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger>
        <Button variant="soft" size="2">
          Configurações
        </Button>
      </Dialog.Trigger>
      <Dialog.Content style={{ maxWidth: 480 }}>
        <Dialog.Title>Configurações de Salvamento</Dialog.Title>
        <Dialog.Description>
          <Text size="2">Escolha quando as edições são persistidas no servidor.</Text>
        </Dialog.Description>
        <Flex direction="column" gap="3" mt="4">
          <RadioGroup.Root
            value={strategy}
            onValueChange={(v) => setStrategy(v as SaveStrategy)}
          >
            <Flex direction="column" gap="2">
              <Text as="label" size="2">
                <Flex gap="2" align="center">
                  <RadioGroup.Item value="auto" />
                  Automático (1.5s após edição)
                </Flex>
              </Text>
              <Text as="label" size="2">
                <Flex gap="2" align="center">
                  <RadioGroup.Item value="per_op" />
                  Por operação
                </Flex>
              </Text>
              <Text as="label" size="2">
                <Flex gap="2" align="center">
                  <RadioGroup.Item value="explicit" />
                  Manual (Ctrl+S)
                </Flex>
              </Text>
            </Flex>
          </RadioGroup.Root>
        </Flex>
        <Flex gap="3" mt="4" justify="end">
          <Dialog.Close>
            <Button variant="soft">Fechar</Button>
          </Dialog.Close>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  )
}
