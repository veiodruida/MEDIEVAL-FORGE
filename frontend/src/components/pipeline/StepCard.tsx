import { Box, Card, Flex, Heading, Text } from '@radix-ui/themes'

interface StepCardProps {
  title: string
  description?: string
  children: React.ReactNode
  footer?: React.ReactNode
}

export function StepCard({ title, description, children, footer }: StepCardProps) {
  return (
    <Card mb="4">
      <Flex direction="column" gap="3">
        <Heading size="4">{title}</Heading>
        {description && (
          <Text size="2" color="gray">
            {description}
          </Text>
        )}
        <Box>{children}</Box>
        {footer && (
          <Flex gap="2" mt="2">
            {footer}
          </Flex>
        )}
      </Flex>
    </Card>
  )
}
