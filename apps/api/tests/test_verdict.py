from datetime import UTC,datetime
from uuid import uuid4
from app.final_assessment_aggregator import FinalAssessmentAggregator
from app.specialist_assessor_models import *
from app.verdict_models import *

def row(kind,strength):
 out=SpecialistAssessmentOutput(assessor_type=kind,status=SpecialistStatus.COMPLETE,signal_strength=strength,confidence=.8,evidence_turn_ids=[uuid4()],reason_summary="Evidence supports this bounded assessment.")
 return StoredSpecialistAssessment(id=uuid4(),session_id=uuid4(),assessor_type=kind,status=SpecialistStatus.COMPLETE,result_json=out,model="m",model_version="m",prompt_version="v1",rubric_version="v1",created_at=datetime.now(UTC))
def test_low_signal_widens_ranges():
 a=FinalAssessmentAggregator(); full=SpecialistAssessmentBundle(session_id=uuid4(),technical=row(AssessorType.TECHNICAL,SignalStrength.MODERATE),behaviour=row(AssessorType.BEHAVIOUR,SignalStrength.MODERATE),claims=row(AssessorType.CLAIMS,SignalStrength.MODERATE)); low=SpecialistAssessmentBundle(session_id=uuid4(),technical=row(AssessorType.TECHNICAL,SignalStrength.MODERATE))
 assert a.aggregate(low).role_readiness_high-a.aggregate(low).role_readiness_low>a.aggregate(full).role_readiness_high-a.aggregate(full).role_readiness_low
def test_p4_role_can_exceed_interview():
 result=FinalAssessmentAggregator().aggregate(SpecialistAssessmentBundle(session_id=uuid4(),technical=row(AssessorType.TECHNICAL,SignalStrength.STRONG),behaviour=row(AssessorType.BEHAVIOUR,SignalStrength.WEAK),claims=row(AssessorType.CLAIMS,SignalStrength.MODERATE)))
 assert result.role_readiness_internal>result.interview_readiness_internal
def test_controlled_dignified_contract():
 assert VerdictCode.NOT_READY_YET.value=="NOT_READY_YET"

