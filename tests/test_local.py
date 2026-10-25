"""Structural checks only. NOT provider validation, not deployment tests."""
from pathlib import Path
import unittest
import ast
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
TIERS = {"medium": "02-medium", "intensive": "03-intensive"}
TOOLS = ("cloudformation", "terraform", "opentofu", "pulumi")
GENERATED_DIRS = {"venv", ".terraform", ".pulumi-state", "__pycache__", "state-backups"}

class Tests(unittest.TestCase):
    def test_file_inventory(self):
        for level in TIERS.values():
            for tool in TOOLS:
                folder = ROOT / "tiers" / level / tool
                self.assertTrue(folder.is_dir(), str(folder))
                primary = ("template.yaml" if tool == "cloudformation" else
                           "__main__.py" if tool == "pulumi" else "main.tf")
                self.assertTrue((folder / primary).is_file(), str(folder / primary))

    def test_yaml_and_python_parse(self):
        for p in ROOT.rglob("*.yaml"):
            if GENERATED_DIRS.intersection(p.relative_to(ROOT).parts):
                continue
            self.assertIsNotNone(yaml.compose(p.read_text(encoding="utf-8")), str(p))
        for p in ROOT.rglob("*.py"):
            if GENERATED_DIRS.intersection(p.relative_to(ROOT).parts):
                continue
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))

    def test_cfn_required_resources(self):
        required = {
            "medium": {"AWS::ECS::Service", "AWS::RDS::DBInstance", "AWS::ECS::TaskDefinition",
                       "AWS::ElasticLoadBalancingV2::LoadBalancer", "AWS::IAM::Role"},
            "intensive": {"AWS::AutoScaling::AutoScalingGroup", "AWS::RDS::DBInstance",
                          "AWS::ElastiCache::ReplicationGroup", "AWS::CloudFront::Distribution",
                          "AWS::EC2::NatGateway", "AWS::CloudWatch::Alarm", "AWS::IAM::Role"},
        }
        for tier, dirname in TIERS.items():
            text = (ROOT / 'tiers' / dirname / 'cloudformation' / 'template.yaml').read_text()
            for typ in required[tier]:
                self.assertIn('Type: ' + typ, text)
            self.assertLess(len(text.encode('utf-8')), 51200)

    def test_hcl_terraform_opentofu_compatible(self):
        for dirname in TIERS.values():
            for part in ('main.tf', 'outputs.tf', 'versions.tf'):
                a = (ROOT / 'tiers' / dirname / 'terraform' / part).read_bytes()
                b = (ROOT / 'tiers' / dirname / 'opentofu' / part).read_bytes()
                self.assertEqual(a, b, f'{dirname}/{part} should be identical')
            variables = (ROOT / 'tiers' / dirname / 'terraform' / 'variables.tf').read_text()
            self.assertIn('terraform', variables)
            variables = (ROOT / 'tiers' / dirname / 'opentofu' / 'variables.tf').read_text()
            self.assertIn('opentofu', variables)

    def test_no_stack_state_in_package(self):
        if any(ROOT.glob("tiers/*/*/terraform.tfstate")) or any(ROOT.glob("tiers/*/*/.pulumi-state")):
            self.skipTest("Clean-package check does not apply to an initialized benchmark workspace")
        for p in ROOT.rglob('*'):
            self.assertNotEqual(p.name, 'terraform.tfstate')
            self.assertNotIn('.pulumi-state', p.parts)

    def test_experiment_inventory(self):
        for tool in TOOLS:
            self.assertTrue((ROOT / 'experiments' / 'failure' / tool).exists())
            self.assertTrue((ROOT / 'experiments' / 'modularity' / tool).exists())
        self.assertTrue((ROOT / 'experiments/state-encryption/opentofu/main.tf').is_file())

if __name__ == '__main__':
    unittest.main()
