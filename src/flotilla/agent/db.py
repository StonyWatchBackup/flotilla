import logging
import json
import time
from flotilla.model import FlotillaUnit
from boto.dynamodb2.exceptions import ItemNotFound

logger = logging.getLogger('flotilla')


class FlotillaAgentDynamo(object):
    """Database interaction for worker/agent component.

    Required table permissions:
    status
        -PutItem
    assignments:
        - GetItem
    revisions:
        - GetItem
    units:
        - BatchGetItem
    """

    def __init__(self, instance_id, service_name, status_table,
                 assignments_table, revisions_table, units_table):
        self._id = instance_id
        self._service = service_name
        self._status = status_table
        self._assignments = assignments_table
        self._revisions = revisions_table
        self._units = units_table

    def store_status(self, unit_status):
        """Store unit status.
        :param unit_status Unit statuses.
        """
        logger.debug('Storing status as %s.', self._id)
        data = {name: json.dumps(status)
                for name, status in unit_status.items()}
        data['service'] = self._service
        data['instance_id'] = self._id
        data['status_time'] = time.time()
        self._status.put_item(data=data, overwrite=True)
        logger.debug('Stored status as %s.', self._id)

    def get_units(self):
        """Get currently assigned FlotillaUnits."""
        units = []
        assigned_revision = self.get_assignment()
        if assigned_revision:
            logger.debug('Assigned: %s, fetching units.', assigned_revision)
            revision_item = self._revisions.get_item(rev_hash=assigned_revision)
            unit_items = self._units.batch_get(keys=[
                {'unit_hash': unit} for unit in revision_item['units']
                ])
            for unit_item in unit_items:
                units.append(FlotillaUnit(unit_item['name'],
                                          unit_item['unit_file'],
                                          unit_item['environment']))

            logger.debug('Assignment %s contained %d units.', assigned_revision,
                         len(units))

        # TODO: global services?
        return units

    def get_assignment(self):
        try:
            assignment = self._assignments.get_item(instance_id=self._id)
            return assignment['assignment']
        except ItemNotFound:
            return None