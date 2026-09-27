import { memo } from 'react'
import { getSmoothStepPath, type EdgeProps } from '@xyflow/react'

function LineageEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 0,
  })

  const isTampered = data?.isTampered === true

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: isTampered ? 'var(--state-tampered)' : 'var(--rule-strong)',
          strokeWidth: 1.5,
          fill: 'none',
          ...style,
        }}
      />
      {isTampered && (
        <path
          d={edgePath}
          style={{
            stroke: 'var(--state-tampered)',
            strokeWidth: 2.5,
            fill: 'none',
            strokeDasharray: '6 12',
            animation: 'dashPulse 1.2s linear infinite',
          }}
        />
      )}
    </>
  )
}

export default memo(LineageEdgeComponent)
